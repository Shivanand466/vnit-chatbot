"""
Tests for the agentic layer: tools, verifier, and the planner's loop.

No API key and no internet needed: the planner is driven by a fake LLM that
replays scripted replies, including the failures seen live while building it
(a 400 "tool_use_failed", a 429 rate limit). The tool tests use the real search
index, so they also confirm the index loads.

    python test_agentic.py        # plain run, prints PASS/FAIL per test
    python -m pytest test_agentic.py   # same tests under pytest, if installed
"""
import json
import sys

import planner
import query
import respond
import router
import tools
import verifier


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

def test_verifier_accepts_figures_in_the_passages():
    r = verifier.verify("The hostel fee is **Rs. 32,650** for Winter 2026.",
                        ["For Girls : Total amount of Rs. 32650/- Winter 2026"])
    assert r["verdict"] == "verified", r


def test_verifier_flags_an_invented_figure():
    r = verifier.verify("The hostel fee is **Rs. 73,000**.", ["Total amount of Rs. 32650/-"])
    assert r["verdict"] == "unsupported" and r["unsupported"] == ["73,000"], r


def test_verifier_accepts_a_worked_calculation():
    r = verifier.verify("Total = 1,25,000 × 4 = 5,00,000.", ["Tuition Fee 125000"])
    assert r["verdict"] == "verified", r


def test_verifier_rejects_wrong_arithmetic():
    r = verifier.verify("Total = 1,25,000 × 4 = 6,00,000.", ["Tuition Fee 125000"])
    assert r["verdict"] == "unsupported", r


def test_verifier_accepts_calculator_results():
    r = verifier.verify("You pay **500000** in total.", ["Tuition Fee 125000"], computed=[500000])
    assert r["verdict"] == "verified", r


def test_verifier_matches_phone_numbers_split_differently():
    r = verifier.verify("Call 1800‑180‑5522.", ["Anti-Ragging Helpline at 1800180 5522"])
    assert r["verdict"] == "verified", r


def test_verifier_checks_emails():
    ok = verifier.verify("Write to deanacd@vnit.ac.in.", ["Email: deanacd@vnit.ac.in"])
    bad = verifier.verify("Write to dean@vnit.ac.in.", ["Email: deanacd@vnit.ac.in"])
    assert ok["verdict"] == "verified" and bad["verdict"] == "unsupported", (ok, bad)


def test_verifier_lakh_and_date_formats():
    r = verifier.verify("It gives **₹1,50,000** a year; apply by 20 September 2026.",
                        ["Scholarship of Rs 1.5 lakh per year. Last date 20/09/2026"])
    assert r["verdict"] == "verified", r


def test_verifier_numbers_from_the_question_are_allowed():
    r = verifier.verify("I couldn't find the hostel fee for 2015-16.", ["nothing relevant"],
                        question="What was the hostel fee in 2015-16?")
    assert r["unsupported"] == [], r


def test_verifier_compares_academic_years_as_units():
    """Seen in the 2026-10-30 run: "2026-27" vs a source's "2026-2027" flagged "27"."""
    ok = verifier.verify("The 2026‑27 brochure lists 70,000.", ["Admissions 2026-2027: Tuition 70,000"])
    bad = verifier.verify("The 2024-25 report lists 70,000.", ["Admissions 2026-2027: Tuition 70,000"])
    assert ok["verdict"] == "verified" and bad["unsupported"] == ["2024-25"], (ok, bad)


def test_verifier_recognises_refusals():
    assert verifier.is_refusal("I couldn’t find the Wi‑Fi password in the documents.")
    assert verifier.is_refusal("None of the provided documents state the total.")
    assert not verifier.is_refusal("The fee is Rs. 32,650.")


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

def test_calculator():
    assert tools.safe_calculate("1,25,000 x 4") == 500000
    assert tools.safe_calculate("(32650 - 32150) / 2") == 250
    assert tools.safe_calculate("₹3,000 × 3") == 9000


def test_calculator_refuses_code():
    for bad in ["__import__('os')", "open('x')", "2 ** 1000", "a + 1"]:
        try:
            tools.safe_calculate(bad)
        except Exception:
            continue
        raise AssertionError(f"accepted {bad!r}")


# ---------------------------------------------------------------------------
# Document tools (real index)
# ---------------------------------------------------------------------------

def test_find_documents_by_title():
    out = tools.run_tool("find_documents", {"keywords": "placement statistics 2025-26"}, tools.Evidence())
    assert "Placement and Internship Report 2025-2026" in out["observation"], out
    assert "Training & Placement" in out["observation"], out


def test_title_matching_respects_programme_and_gender():
    out = tools.matching_titles("What is the hostel fee for first year B.Tech girls for Winter 2026?")
    first = out.splitlines()[1]
    assert "GIRLS" in first and "M.Tech" not in first, out


def test_read_document_finds_what_corpus_wide_search_buries():
    """EXPERIMENTS-LOG §16: the 2025-26 placement figures rank 293rd corpus-wide."""
    tnp = next(i for i, s in enumerate(query.list_sources()) if s["url"].endswith("/section/tnp/"))
    out = tools.run_tool("read_document", {"document_id": f"S{tnp}",
                                           "query": "How many students were placed in 2025-26 and how "
                                                    "many companies visited?"}, tools.Evidence())
    assert "678" in out["observation"] and "170" in out["observation"], out["observation"][:500]


def test_bad_tool_calls_become_observations():
    ev = tools.Evidence()
    assert "Error" in tools.run_tool("read_document", {"document_id": "S99999", "query": "x"}, ev)["observation"]
    assert "Error" in tools.run_tool("no_such_tool", {}, ev)["observation"]
    assert "Error" in tools.run_tool("calculate", {"expression": "import os"}, ev)["observation"]


def test_evidence_labels_repeat_passages_by_label_only():
    ev = tools.Evidence()
    r = {"source_url": "https://vnit.ac.in/x", "title": "X", "text": "Some passage text", "fetched": ""}
    first = ev.render([r])
    again = ev.render([r])
    assert first.startswith("[P1 ·") and again == "[P1] (already shown above)", (first, again)


# ---------------------------------------------------------------------------
# Planner loop, driven by a fake LLM
# ---------------------------------------------------------------------------

PASSAGE = {"source_url": "https://drive.google.com/file/d/abc/view", "title": "HOSTEL FEES GIRLS",
           "text": "For Girls : Total amount of Rs. 32650/- Winter 2026", "fetched": "2026-04-10",
           "score": 0.5}
REPORT = {"question": "What is the girls' hostel fee?",
          "sub_questions": [{"sub_question": "What is the girls' hostel fee?",
                             "results": [PASSAGE], "conflict_warning": None}]}


class _Resp:
    def __init__(self, status, body=None, text=""):
        self.status_code = status
        self._body = body or {}
        self.text = text or json.dumps(self._body)
        self.headers = {"x-ratelimit-remaining-tokens": "8000", "x-ratelimit-limit-tokens": "8000"}

    def json(self):
        return self._body


def _reply(content="", tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return _Resp(200, {"choices": [{"message": msg}], "usage": {"total_tokens": 100}})


def _call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _run_with(replies, question="What is the girls' hostel fee?"):
    import requests

    sent = []
    queue = list(replies)
    original = requests.post

    def fake_post(url, **kw):
        sent.append(kw["json"])
        return queue.pop(0)

    requests.post = fake_post
    try:
        return planner.run(question, REPORT, api_key="test-key"), sent
    finally:
        requests.post = original


def test_planner_answers_directly_and_verifies():
    out, sent = _run_with([_reply("**Rs. 32,650** for Winter 2026 [P1].")])
    assert len(sent) == 1 and "tools" in sent[0]
    assert out["answer"].startswith("**Rs. 32,650**") and "[1]" in out["answer"], out["answer"]
    assert out["verification"]["verdict"] == "verified"
    assert out["sources"][0]["title"] == "HOSTEL FEES GIRLS"
    assert out["mode"].startswith("agent")


def test_planner_uses_a_tool_then_answers():
    out, sent = _run_with([
        _reply(tool_calls=[_call("calculate", {"expression": "32650 * 2"})]),
        _reply("Two sessions cost **Rs. 65,300** [P1]."),
    ])
    steps = [t["step"] for t in out["trace"]]
    assert "tool" in steps, out["trace"]
    assert sent[1]["messages"][-1]["role"] == "tool"
    assert out["verification"]["verdict"] == "verified", out["verification"]


def test_planner_revises_an_unsupported_figure():
    out, sent = _run_with([
        _reply("The fee is **Rs. 73,000** [P1]."),
        _reply("The fee is **Rs. 32,650** [P1]."),
    ])
    assert "73,000" not in out["answer"] and out["verification"]["verdict"] == "verified", out
    assert any(t["step"] == "revise" for t in out["trace"])
    assert "tools" not in sent[1], "the revision must not offer tools"


def test_planner_flags_what_it_cannot_fix():
    out, _ = _run_with([_reply("The fee is **Rs. 73,000** [P1]."),
                        _reply("The fee is **Rs. 73,000** [P1].")])
    assert "could not confirm 73,000" in out["answer"], out["answer"]


def test_planner_recovers_from_tool_use_failed():
    """Seen live: gpt-oss called a tool it was not offered, and Groq returned 400."""
    out, sent = _run_with([
        _Resp(400, text='{"error":{"code":"tool_use_failed"}}'),
        _reply("**Rs. 32,650** [P1]."),
    ])
    assert "tools" not in sent[1] and all(m["role"] != "tool" for m in sent[1]["messages"])
    assert out["verification"]["verdict"] == "verified"


def test_planner_numbers_bold_citations():
    """Seen live: the model wrote [**P1**], which was left in the answer as text."""
    out, _ = _run_with([_reply("**Rs. 32,650** [**P1**].")])
    assert "P1" not in out["answer"] and "[1]" in out["answer"], out["answer"]


def test_planner_drops_citations_to_unseen_passages():
    out, _ = _run_with([_reply("**Rs. 32,650** [P1][P9].")])
    assert "P9" not in out["answer"] and any("P9" in t["text"] for t in out["trace"]), out


def test_retry_after_reads_minutes():
    """Seen live: "12m3.2s" was read as 3.2 seconds."""
    assert planner._retry_after(_Resp(429, text="Please try again in 12m3.2s.")) == 723.2
    assert planner._retry_after(_Resp(429, text="Please try again in 7.5s.")) == 7.5


def test_planner_stops_at_once_on_the_daily_limit():
    daily = _Resp(429, text='{"error":{"message":"Rate limit reached on tokens per day (TPD): '
                            'Limit 200000. Please try again in 12m3.2s."}}')
    try:
        _run_with([daily])
    except planner.AgentUnavailable as e:
        assert "daily allowance" in str(e)
        return
    raise AssertionError("daily limit not reported")


def test_respond_falls_back_when_the_agent_cannot_run():
    """No key: the agent declines, the one-shot path quotes passages, nothing crashes."""
    import os

    saved = os.environ.pop("GENAI_API_KEY", None)
    try:
        out = respond.answer("What is the hostel fee for first year B.Tech girls for Winter 2026?",
                             use_agent=True)
    finally:
        if saved is not None:
            os.environ["GENAI_API_KEY"] = saved
    assert out["mode"].startswith("extractive"), out["mode"]
    assert any(t["step"] == "fallback" for t in out["trace"]), out["trace"]


def test_respond_greeting_skips_search():
    out = respond.answer("hello")
    assert out["mode"] == "direct (greeting)" and out["trace"][-1]["step"] == "route"
    assert out["intent"] is None


# ---------------------------------------------------------------------------
# Topic intent
# ---------------------------------------------------------------------------

def test_intent_of_the_answer_check_questions():
    import check_answers
    expected = {
        "hostel_fee_first_year": "hostel", "hostel_fee_girls": "hostel",
        "unanswerable_wifi": "hostel", "hostel_appliances": "hostel",
        "btech_fee_open": "fees", "mtech_fee_scst": "fees", "summer_term_fee": "fees",
        "director": "people", "dean_academic_email": "people", "registrar": "people",
        "antiragging_helpline": "people",
        "placements": "placement",
        "kotak_scholarship": "scholarship", "idfc_deadline": "scholarship",
        "classes_start_fy": "calendar", "endsem_fy": "calendar", "midsem_slot_a": "calendar",
        "chemical_spec": "department", "mech_established": "department",
        "unanswerable_1995": "other",
    }
    questions = {name: q for name, q, _m, _n in check_answers.CHECKS}
    wrong = {name: router.intent(questions[name]) for name in expected
             if router.intent(questions[name]) != expected[name]}
    assert not wrong, wrong


def test_intent_priority_order():
    # Hostel before fees, scholarship before calendar: the more specific topic wins.
    assert router.intent("What is the mess fee?") == "hostel"
    assert router.intent("Last date for the scholarship form?") == "scholarship"
    assert router.intent("Attendance rules for the end sem exam") == "calendar"
    assert router.intent("What is the attendance rule?") == "rules"


def test_respond_reports_the_intent_in_the_trace():
    import os
    saved = os.environ.pop("GENAI_API_KEY", None)
    try:
        out = respond.answer("Who is the Registrar of VNIT?", use_agent=False)
    finally:
        if saved is not None:
            os.environ["GENAI_API_KEY"] = saved
    assert out["intent"] == "people", out["intent"]
    assert {"step": "route", "text": "Topic: people."} in out["trace"], out["trace"]


# ---------------------------------------------------------------------------
# Corrective retrieval gate
# ---------------------------------------------------------------------------

PLACEMENTS = "How many students got placed in 2025-26 and how many companies came?"

# Top-7 chunk ids before the reranker's scores were kept (30 Oct 2026, index of
# 8,162 chunks): keeping the scores must not change the order. Rebuilding the
# index renumbers chunks, so these need updating after build_index.py.
RANKING_SNAPSHOT = {
    "Who is the current Director of VNIT?": [110, 106, 7245, 107, 2612, 80, 7029],
    "What is the hostel fee for first year B.Tech girls for the Winter 2026 session?":
        [2921, 2925, 2918, 2923, 6600, 2448, 5962],
    PLACEMENTS: [6446, 3468, 3469, 3467, 6444, 6449, 6438],
}


def test_keeping_rerank_scores_leaves_the_order_unchanged():
    chunks = query.load_index()["chunks"]
    if len(chunks) != 8162:
        return  # a rebuilt index numbers chunks differently; the snapshot no longer applies
    position = {(c["source_url"], c["text"]): i for i, c in enumerate(chunks)}
    for question, ids in RANKING_SNAPSHOT.items():
        results = query.retrieve(question, k=7)
        assert [position[(r["source_url"], r["text"])] for r in results] == ids, question
        scores = [r["rerank"] for r in results]
        assert scores == sorted(scores, reverse=True), scores


def test_grade_separates_a_weak_first_search():
    import agent
    import grader
    weak = grader.grade(PLACEMENTS, agent.answer(PLACEMENTS))
    good = grader.grade("Who is the current Director of VNIT?",
                        agent.answer("Who is the current Director of VNIT?"))
    old_year = "What was the hostel fee for first year B.Tech boys in 2015-16?"
    other_year = grader.grade(old_year, agent.answer(old_year))
    assert weak["grade"] != "correct", weak
    assert good["grade"] == "correct", good
    assert other_year["grade"] != "correct" and "2015-16" in other_year["why"], other_year


def test_gate_puts_the_placement_figures_in_front_of_the_agent():
    import os
    import requests

    sent = []

    def fake_post(url, **kw):
        sent.append(kw["json"])
        return _reply("The figures are not in the passages.")

    original, saved = requests.post, os.environ.get("GENAI_API_KEY")
    requests.post, os.environ["GENAI_API_KEY"] = fake_post, "test-key"
    try:
        out = respond.answer(PLACEMENTS, use_agent=True)
    finally:
        requests.post = original
        if saved is None:
            os.environ.pop("GENAI_API_KEY")
        else:
            os.environ["GENAI_API_KEY"] = saved
    first_prompt = sent[0]["messages"][1]["content"]
    assert "678" in first_prompt and "Search quality:" in first_prompt, first_prompt[-400:]
    grade_steps = [t for t in out["trace"] if t["step"] == "grade"]
    assert grade_steps and "Training & Placement" in grade_steps[0]["text"], out["trace"]
    assert out["trace"].index(grade_steps[0]) > 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {str(e)[:300]}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
