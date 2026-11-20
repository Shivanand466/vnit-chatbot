"""
Tests for agent v2 (Runbook 11): memory, the loop, the new tools, task types,
languages and streaming.

Like test_agentic.py, no API key and no internet: every LLM reply is scripted
by a fake that stands in for requests.post, and the live-page tool reads a
saved HTML file. test_agentic.py runs these too, so one command checks v1 and
v2 together.

    python test_agent_v2.py
"""
import json
import os
import sys

import followup
import memory
import planner
import respond


# ---------------------------------------------------------------------------
# A fake LLM: scripted replies, recorded requests
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status=200, body=None, text="", lines=None):
        self.status_code = status
        self._body = body or {}
        self.text = text or json.dumps(self._body)
        self.headers = {"x-ratelimit-remaining-tokens": "8000", "x-ratelimit-limit-tokens": "8000"}
        self._lines = lines

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_lines(self, decode_unicode=True):
        for line in self._lines or []:
            yield line

    def close(self):
        pass


def reply(content="", tool_calls=None, tokens=100):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return FakeResponse(200, {"choices": [{"message": msg}], "usage": {"total_tokens": tokens}})


def call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class FakeLLM:
    """Stands in for requests.post. Each reply is a FakeResponse or a function of the payload."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def __call__(self, url, **kw):
        self.sent.append(json.loads(json.dumps(kw["json"])))   # as sent, not as later changed
        nxt = self.replies.pop(0) if self.replies else reply("(no more scripted replies)")
        return nxt(kw["json"]) if callable(nxt) else nxt

    def __enter__(self):
        import requests
        self._original = requests.post
        requests.post = self
        return self

    def __exit__(self, *exc):
        import requests
        requests.post = self._original


def with_env(flags, fn):
    saved = {k: os.environ.get(k) for k in flags}
    for k, v in flags.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


PASSAGE = {"text": "HOSTEL FEES FOR FIRST YEAR GIRLS. For Girls : Total amount of Rs. 32650/- Winter 2026",
           "title": "HOSTEL FEES GIRLS", "source_url": "https://drive.google.com/file/d/girls/view",
           "fetched": "2026-06-01", "rerank": 6.0, "score": 0.5}
REPORT = {"question": "What is the girls' hostel fee?",
          "sub_questions": [{"sub_question": "What is the girls' hostel fee?",
                             "results": [PASSAGE], "conflict_warning": None}]}

FEE_TURN = {"q": "What is the B.Tech tuition fee for Winter 2026?",
            "a": "The B.Tech tuition fee for Winter 2026 is **Rs. 62,500** per semester [1].\n\n"
                 "**Who can help:** Accounts Section — ar_accounts@vnit.ac.in"}


# ---------------------------------------------------------------------------
# Step 1: conversation memory
# ---------------------------------------------------------------------------

def test_memory_keeps_six_turns():
    six = [{"q": f"question {i}", "a": f"answer {i}"} for i in range(6)]
    seven = six + [{"q": "question 6", "a": "answer 6"}]
    assert memory.clean_turns(six) == six
    kept = memory.clean_turns(seven)
    assert len(kept) == 6 and kept[0]["q"] == "question 1" and kept[-1]["q"] == "question 6", kept


def test_memory_token_cap_drops_the_oldest():
    long = [{"q": f"q{i} " + "word " * 95, "a": "fee " * 300} for i in range(6)]
    kept = memory.clean_turns(long)
    assert 0 < len(kept) < 6 and kept[-1]["q"].startswith("q5"), [t["q"][:3] for t in kept]
    assert len(memory.block(kept)) / memory.CHARS_PER_TOKEN <= memory.MAX_TOKENS
    assert kept[0]["q"].startswith(f"q{6 - len(kept)}")


def test_memory_trims_answers_and_drops_sources():
    kept = memory.clean_turns([FEE_TURN, {"q": "x", "a": "y " * 1000}, "not a dict", {"a": "no q"}])
    assert len(kept) == 2, kept
    assert "[1]" not in kept[0]["a"] and "Who can help" not in kept[0]["a"], kept[0]
    assert len(kept[1]["a"]) <= memory.ANSWER_CHARS + 3


def test_pay_it_after_a_fee_answer_names_the_programme():
    def rewrite(payload):
        prompt = payload["messages"][0]["content"]
        # The fake model can only name the fee if it was shown the earlier answer.
        ok = "Rs. 62,500" in prompt and "Assistant:" in prompt
        return reply("How do I pay the B.Tech tuition fee for Winter 2026?" if ok else "How do I pay it?")

    with FakeLLM([rewrite]) as fake:
        q, note = followup.resolve("how do I pay it?", [FEE_TURN["q"]], api_key="k",
                                   turns=memory.clean_turns([FEE_TURN]))
    assert "B.Tech" in q and note == "rewritten" and len(fake.sent) == 1, q
    # With no key, the code fallback still keeps the programme's words.
    q, _ = followup.resolve("how do I pay it?", [FEE_TURN["q"]], turns=[FEE_TURN])
    assert "B.Tech" in q, q


def test_item_references_are_follow_ups_only_with_answers():
    assert followup.looks_like_followup("Which of those is cheaper?")
    assert followup.looks_like_followup("the second one", answers_remembered=True)
    assert followup.looks_like_followup("which one is cheaper?", answers_remembered=True)
    assert not followup.looks_like_followup("the second one")          # v1 unchanged


def test_earlier_answers_are_never_evidence():
    conversation = memory.prompt_block([{"q": "hostel fee?", "a": "It is Rs. 73,000."}])
    with FakeLLM([reply("The fee is **Rs. 73,000** [P1]."),
                  reply("The fee is **Rs. 73,000** [P1].")]) as fake:
        out = with_env({"AGENT_V2": "off"}, lambda: planner.run(
            "What is the girls' hostel fee?", REPORT, api_key="k", conversation=conversation))
    assert "Conversation so far" in fake.sent[0]["messages"][1]["content"]
    assert out["verification"]["verdict"] == "unsupported", out["verification"]


def _first_prompt(flags, turns):
    with FakeLLM([reply("**Rs. 32,650** [P1].")] * 3) as fake:
        with_env(dict(flags, GENAI_API_KEY="test-key"), lambda: respond.answer(
            "What is the hostel fee for first year B.Tech girls for Winter 2026?",
            use_agent=True, turns=turns))
    return fake.sent[0]["messages"][1]["content"]


def test_agent_v2_off_ignores_the_answers():
    turns = [{"q": "Who is the Director?", "a": "Prof. Prem Lal Patel."}]
    on = _first_prompt({"AGENT_V2": "on"}, turns)
    off = _first_prompt({"AGENT_V2": "off"}, turns)
    assert "Conversation so far" in on and "Prem Lal Patel" in on
    assert "Conversation so far" not in off and "Prem Lal Patel" not in off
    assert off == _first_prompt({"AGENT_V2": "off"}, []), "v1 with turns must equal v1 without"


# ---------------------------------------------------------------------------
# Step 2: the loop
# ---------------------------------------------------------------------------

class FakeTools:
    """Stands in for tools.run_tool: optional passages per call, records concurrency."""

    def __init__(self, passages_for=None, delay=0.0):
        import threading
        self.passages_for = passages_for or (lambda name, args: [])
        self.delay, self.running, self.most, self.calls = delay, 0, 0, []
        self._lock = threading.Lock()

    def __call__(self, name, args, evidence):
        import time
        with self._lock:
            self.running += 1
            self.most = max(self.most, self.running)
            self.calls.append(name)
        time.sleep(self.delay)
        rendered = evidence.render(self.passages_for(name, args))
        with self._lock:
            self.running -= 1
        return {"observation": rendered or "No passages found.", "summary": f"ran {name}"}

    def __enter__(self):
        import tools
        self._original = tools.run_tool
        tools.run_tool = self
        return self

    def __exit__(self, *exc):
        import tools
        tools.run_tool = self._original


def _passage(text, title="Fee notice", url="https://drive.google.com/file/d/x/view"):
    return {"text": text, "title": title, "source_url": url, "fetched": "2026-06-01",
            "rerank": 5.0, "score": 0.5}


def _loop(replies, question="What is the girls' hostel fee?", flags=None, fake_tools=None, **kw):
    import agent_loop
    with FakeLLM(replies) as fake, (fake_tools or FakeTools()) as ft:
        out = with_env(flags or {}, lambda: agent_loop.run(question, REPORT, api_key="k", **kw))
    return out, fake, ft


def test_loop_four_rounds_with_parallel_calls():
    counter = iter(range(100))

    def found(name, args):
        return [_passage(f"Unrelated notice number {next(counter)} about the zebra crossing.",
                         url=f"https://drive.google.com/file/d/{args['n']}/view")]

    replies = [reply("1. Find the yearly zebra levy.\n2. Find the zebra levy due date.",
                     [call("search_vnit", {"query": "a", "n": i}, f"c{i}") for i in range(3)])]
    replies += [reply("", [call("search_vnit", {"query": "b", "n": 10 + i})]) for i in range(3)]
    replies += [reply("The fee is **Rs. 32,650** [P1].")]
    out, fake, ft = _loop(replies, fake_tools=FakeTools(found, delay=0.3))
    assert out["usage"]["steps"] == 4 and out["usage"]["tool_calls"] == 6, out["usage"]
    assert ft.most == 3, f"round one's three calls should run together, most at once: {ft.most}"
    assert [t["step"] for t in out["trace"]].count("plan") == 1
    assert out["usage"]["plan_parts"] == 2
    assert "Steps left: 5" in fake.sent[1]["messages"][-1]["content"], fake.sent[1]["messages"][-1]
    assert out["verification"]["verdict"] == "verified"


def test_loop_stops_on_the_budget():
    replies = [reply("1. Find the levy.", [call("search_vnit", {"query": "a"})], tokens=7500),
               reply("The fee is **Rs. 32,650** [P1].")]
    out, fake, _ = _loop(replies, flags={"AGENT_V2_BUDGET": "9000"},
                         fake_tools=FakeTools(lambda n, a: [_passage("A new zebra passage.")]))
    assert len(fake.sent) == 2 and "tools" not in fake.sent[1], "one round, then the final answer"
    assert any(t["step"] == "stop" and "budget" in t["text"] for t in out["trace"]), out["trace"]


def test_loop_stops_when_stuck_and_says_why():
    replies = [reply("1. Find the levy.", [call("search_vnit", {"query": "a"})]),
               reply("", [call("search_vnit", {"query": "b"})]),
               reply("I could not find the levy in VNIT's documents.")]
    out, fake, ft = _loop(replies)
    assert ft.calls == ["search_vnit", "search_vnit"], ft.calls
    reflections = [t["text"] for t in out["trace"] if t["step"] == "reflect"]
    assert reflections and "nothing new" in reflections[0], out["trace"]
    assert any(t["step"] == "stop" and "nothing new" in t["text"] for t in out["trace"])
    assert "tools" not in fake.sent[-1]


def test_loop_tracks_plan_parts_and_stops_when_all_are_done():
    fee = _passage("HOSTEL FEES FOR FIRST YEAR M.Tech BOYS. Total hostel fee Rs. 40,080 per year.",
                   title="Hostel fees M.Tech")
    date = _passage("Hostel fee due date: the last date for payment is 15/07/2026.",
                    title="Hostel fee notice",
                    url="https://drive.google.com/file/d/due/view")
    replies = [reply("1. Find the M.Tech hostel fee.\n2. Find the hostel fee due date.",
                     [call("lookup_table", {"keywords": "mtech hostel fee"}, "a"),
                      call("search_vnit", {"query": "hostel fee last date"}, "b")]),
               reply("**Rs. 40,080** [P2], due by **15/07/2026** [P3].")]
    out, fake, _ = _loop(replies, question="M.Tech hostel fee and when is it due?",
                         fake_tools=FakeTools(lambda n, a: [fee] if n == "lookup_table" else [date]))
    assert out["usage"]["plan_done"] == 2 and out["usage"]["steps"] == 1, out["usage"]
    assert any(t["step"] == "stop" and "plan" in t["text"] for t in out["trace"])
    assert len(fake.sent) == 2 and "tools" not in fake.sent[1]
    assert out["verification"]["verdict"] == "verified", out["verification"]


def test_a_repeated_tool_call_is_not_run_again():
    same = call("read_document", {"document_id": "S1", "query": "last date"})
    replies = [reply("1. Find the levy date.", [same]), reply("", [same]), reply("Not found in the documents.")]
    out, fake, ft = _loop(replies, fake_tools=FakeTools(lambda n, a: [_passage("Zebra levy notice, no date.")]))
    assert ft.calls == ["read_document"], ft.calls
    assert any("Skipped a repeat" in t["text"] for t in out["trace"]), out["trace"]
    assert "already made exactly this call" in fake.sent[2]["messages"][-2]["content"]


def test_model_can_mark_parts_done_itself():
    import agent_loop
    assert agent_loop.parse_done("Done: 1, 3. Still looking for 2.") == {1, 3}
    assert agent_loop.parse_plan("Plan:\n1. Find the fee.\n2) Find the date.\nDone: 1") == \
        ["Find the fee.", "Find the date."]
    assert agent_loop.strip_think("<think>hmm</think>Answer") == "Answer"


def test_loop_still_verifies_and_revises():
    out, fake, _ = _loop([reply("The fee is **Rs. 73,000** [P1]."),
                          reply("The fee is **Rs. 32,650** [P1].")])
    assert out["verification"]["verdict"] == "verified" and "73,000" not in out["answer"]
    assert any(t["step"] == "revise" for t in out["trace"])


def test_agent_v2_switch_picks_the_loop():
    import agent_loop
    used = []

    def recorder(name):
        def run(q, report, **kw):
            used.append(name)
            return {"answer": "**Rs. 32,650** [1]", "sources": [], "mode": f"agent ({name})", "trace": [],
                    "verification": {"verdict": "verified"}, "usage": {}}
        return run

    real, real_v2 = planner.run, agent_loop.run
    planner.run, agent_loop.run = recorder("v1"), recorder("v2")
    try:
        q = "What is the hostel fee for first year B.Tech girls for Winter 2026?"
        on = with_env({"AGENT_V2": "on"}, lambda: respond.answer(q, use_agent=True))
        off = with_env({"AGENT_V2": "off"}, lambda: respond.answer(q, use_agent=True))
    finally:
        planner.run, agent_loop.run = real, real_v2
    assert used == ["v2", "v1"], used
    assert "suggestions" in on and "task" in on
    assert "suggestions" not in off and "task" not in off and "language" not in off


def test_loop_compacts_a_long_conversation():
    import agent_loop
    import tools
    ev = tools.Evidence()
    for i in range(30):
        ev.add(_passage(f"passage {i} " + "x" * 900, title=f"Doc {i}",
                        url=f"https://drive.google.com/file/d/{i}/view"), f"passage {i} " + "x" * 900)
    text, aside = agent_loop.compact("q?", ev, cited={"P2"})
    assert "[P2 " in text and aside and "Set aside" in text, aside[:3]
    assert len(text) < agent_loop.COMPACT_CHARS + 3000


# ---------------------------------------------------------------------------
# Step 3: new tools
# ---------------------------------------------------------------------------

def test_latest_notices_newest_first_and_by_category():
    import tools
    rows = tools.latest_notices("", 8)
    days = [r["fetched"] for r in rows]
    assert len(rows) == 8 and days == sorted(days, reverse=True), days
    fees = tools.latest_notices("fees", 5)
    assert fees and all(re_fee(r["title"]) for r in fees), [r["title"] for r in fees]
    assert all(r["source_url"].startswith("http") for r in fees)


def re_fee(title):
    import re
    return re.search(r"fees?|payment|remission|refund|tuition|challan", title, re.I)


def test_fetch_vnit_page_refuses_other_hosts():
    import tools
    for url in ("https://google.com/", "https://vnit.ac.in.evil.com/x", "https://evilvnit.ac.in/",
                "ftp://vnit.ac.in/", "javascript:alert(1)"):
        assert tools.vnit_url(url) is None, url
        out = tools.run_tool("fetch_vnit_page", {"url": url}, tools.Evidence())
        assert out["observation"].startswith("Refused"), (url, out)
    assert tools.vnit_url("https://vnit.ac.in/section/hostel/")
    assert tools.vnit_url("https://students.vnit.ac.in/notice")


def test_fetch_vnit_page_parses_a_saved_page_and_caches_it():
    import tempfile
    from pathlib import Path
    import tools

    html = (Path(__file__).parent / "fixtures" / "vnit_section_hostel.html").read_text(encoding="utf-8")
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        return html

    saved = tools.PAGE_CACHE
    with tempfile.TemporaryDirectory() as tmp:
        tools.PAGE_CACHE = Path(tmp)
        try:
            first = tools.fetch_vnit_page("https://vnit.ac.in/section/hostel/", fetch=fake_fetch)
            again = tools.fetch_vnit_page("https://vnit.ac.in/section/hostel/", fetch=fake_fetch)
        finally:
            tools.PAGE_CACHE = saved
    assert first["from"] == "live" and again["from"] == "cache" and len(fetched) == 1
    assert "Hostel" in first["title"] and "Refund" in first["text"], first["title"]
    assert len(first["text"]) <= tools.PAGE_CHARS


def test_fetch_vnit_page_falls_back_to_the_crawled_copy():
    import tempfile
    from pathlib import Path
    import tools

    def offline(url):
        raise ConnectionError("no internet")

    url = next(s["url"] for s in tools._catalogue() if "vnit.ac.in" in s["url"] and s["chunk_ids"])
    saved = tools.PAGE_CACHE
    with tempfile.TemporaryDirectory() as tmp:
        tools.PAGE_CACHE = Path(tmp)
        try:
            page = tools.fetch_vnit_page(url, fetch=offline)
        finally:
            tools.PAGE_CACHE = saved
    assert page["from"] == "crawl" and page["text"], page


def test_today_is_ist_and_trusted_as_a_passage():
    import re
    import tools
    ev = tools.Evidence()
    out = tools.run_tool("today", {}, ev)
    assert re.search(r"\d{2} \w+ 20\d{2}", out["summary"]), out
    assert ev.passages and "[P1" in out["observation"]
    day = tools.today_ist()
    check = __import__("verifier").verify(f"Today is {day:%d/%m/%Y}.", [ev.passages[0]["text"]])
    assert check["verdict"] == "verified", check


def test_contact_office_for_hostel():
    import tools
    ev = tools.Evidence()
    out = tools.run_tool("contact_office", {"topic": "hostel room refund"}, ev)
    assert "Hostel Section" in out["summary"] and "AR_HOSTEL@vnit.ac.in" in ev.passages[0]["text"], out
    assert "[P1" in out["observation"]


def test_v2_tools_offered_only_to_v2():
    import tools
    v1 = {s["function"]["name"] for s in tools.active_schemas()}
    v2 = {s["function"]["name"] for s in tools.active_schemas(v2=True)}
    assert not v1 & {"latest_notices", "fetch_vnit_page", "today", "contact_office"}
    assert {"latest_notices", "fetch_vnit_page", "today", "contact_office"} <= v2
    off = with_env({"LIVE_PAGES": "off"}, lambda: {s["function"]["name"] for s in tools.active_schemas(v2=True)})
    assert "fetch_vnit_page" not in off and "today" in off
    for s in tools.V2_SCHEMAS:
        assert len(s["function"]["description"].split()) <= 25, s["function"]["name"]


# ---------------------------------------------------------------------------
# Step 4: task types
# ---------------------------------------------------------------------------

TASK_PHRASINGS = {
    "What is the hostel fee for first year B.Tech girls?": "lookup",
    "Who is the Director of VNIT?": "lookup",
    "When does the winter semester start?": "lookup",
    "fees for B.Tech vs B.Arch": "compare",
    "Compare the M.Tech and MBA tuition fees": "compare",
    "which hostel is cheaper?": "compare",
    "What is the difference between the OPEN and SC/ST tuition fee?": "compare",
    "summarise the hostel rules": "summarise",
    "What does the S-27 fee notice say?": "summarise",
    "Give me the key points of the placement policy": "summarise",
    "how do I apply for fee remission?": "explain",
    "steps to get a bonafide certificate": "explain",
    "What is the procedure for course registration?": "explain",
    "how to pay the hostel fee online": "explain",
    "write an email to the hostel warden asking for a fee extension": "draft",
    "Draft an application to the Dean for a bonafide certificate": "draft",
    "compose a letter to the registrar about my transcript": "draft",
    "what is CGPA?": "general",
    "what does DASA mean?": "general",
    "What is an elective?": "general",
    "define backlog": "general",
    "hello": "chat",
    "thanks!": "chat",
    "what can you do?": "chat",
    "what is the GATE cutoff score for M.Tech CSE at VNIT?": "lookup",
}

MUST_DECLINE = [
    "Who won the VNIT cricket match against IIT Bombay in 1995?",
    "What is the hostel wifi password?",
    "What was the hostel fee for first year B.Tech boys in 2015-16?",
    "What is the monthly salary of the VNIT Director?",
    "How much does a day scholar bus pass cost at VNIT?",
    "what jee main rank do i need for cse at vnit?",
    "What is the GATE cutoff score for M.Tech CSE at VNIT?",
    "what was the average package at vnit in 2015-16?",
    "what is the home address of the hostel warden?",
    "What was the B.Tech tuition fee at VNIT in 1990?",
    # phrased to tempt the general path
    "what was the JoSAA closing rank for CSE at VNIT?",
    "what is the JoSAA closing rank for CSE?",
    "what is the wifi password?",
    "what is the GATE cutoff?",
]


def test_task_types_of_25_phrasings():
    import router
    wrong = {q: (router.task(q), want) for q, want in TASK_PHRASINGS.items() if router.task(q) != want}
    assert len(TASK_PHRASINGS) >= 25 and not wrong, wrong


def test_must_decline_questions_are_never_general():
    import router
    for q in MUST_DECLINE:
        assert router.task(q) != "general", q
        assert router.route(q) == router.LOOKUP, q
    import check_answers
    declines = [c for c in check_answers.CHECKS if c[0].startswith("unanswerable_")]
    assert len(declines) == 10 and all(router.task(c[1]) != "general" for c in declines)


def test_a_draft_gets_the_office_email_and_it_is_verified():
    import router
    draft = ("Draft — check before sending.\n\nTo: AR_HOSTEL@vnit.ac.in [P2]\n\nDear Sir/Madam,\n"
             "I request an extension of the hostel fee deadline.\n\nYours sincerely,\n[Your name]\n[Roll number]")
    replies = [reply("1. Find the hostel office's email.", [call("contact_office", {"topic": "hostel fee"})]),
               reply(draft)]
    import tools
    with FakeLLM(replies) as fake:
        out = with_env({}, lambda: __import__("agent_loop").run(
            "write an email to the hostel office asking for a fee extension", REPORT, api_key="k",
            instructions=[router.TASK_LINES["draft"]]))
    assert "Task: draft" in fake.sent[0]["messages"][0]["content"]
    assert "AR_HOSTEL@vnit.ac.in" in out["answer"] and out["verification"]["verdict"] == "verified", out
    assert any(s["url"] == "https://vnit.ac.in/administrative-officers" for s in out["sources"])
    assert respond.label_draft("Dear Sir,") .startswith("Draft — check before sending.")
    assert respond.label_draft(draft) == draft


def test_a_compare_answer_is_a_table():
    import router
    table = ("| Programme | Tuition fee |\n|---|---|\n| B.Tech | Rs. 32,650 [P1] |\n"
             "| B.Arch | Rs. 32,650 [P1] |")
    with FakeLLM([reply(table)]) as fake:
        out = __import__("agent_loop").run("girls hostel fee B.Tech vs B.Arch", REPORT, api_key="k",
                                           instructions=[router.TASK_LINES["compare"]])
    assert "markdown table" in fake.sent[0]["messages"][0]["content"]
    rows = [l for l in out["answer"].splitlines() if l.startswith("|")]
    assert len(rows) == 4 and "[1]" in rows[2] and rows[1].startswith("|---"), out["answer"]


def test_general_answers_are_labelled_and_carry_no_vnit_figures():
    replies = [reply("CGPA is the Cumulative Grade Point Average, on a 10-point scale.")]
    with FakeLLM(replies) as fake:
        out = with_env({"GENAI_API_KEY": "k"}, lambda: respond.answer("what is CGPA?", use_agent=True))
    assert out["answer"].startswith(respond.GENERAL_LABEL) and out["sources"] == [], out["answer"]
    assert out["mode"].startswith("general") and "Task: general" in " ".join(t["text"] for t in out["trace"])
    assert "VNIT" in fake.sent[0]["messages"][0]["content"]
    with FakeLLM([reply("At VNIT the fee is Rs. 62,500 a semester.")]):
        bad = with_env({"GENAI_API_KEY": "k"}, lambda: respond.answer("what is CGPA?", use_agent=True))
    assert bad["verification"]["verdict"] == "unsupported" and "62,500" in bad["answer"]
    assert "not checked against VNIT's documents" in bad["answer"]


def test_capability_answer_lists_the_new_abilities():
    out = respond.answer("what can you do?")
    assert out["mode"] == "direct (capability)"
    for word in ("compare", "summarise", "draft", "Hindi"):
        assert word in out["answer"], word
    v1 = with_env({"AGENT_V2": "off"}, lambda: respond.answer("what can you do?"))
    assert v1["answer"] == respond.CAPABILITY_ANSWER


# ---------------------------------------------------------------------------
# Step 5: Hindi, Marathi, Hinglish
# ---------------------------------------------------------------------------

LANGUAGE_PHRASINGS = {
    "हॉस्टल की फीस कितनी है?": "hi",
    "बी.टेक की ट्यूशन फीस क्या है?": "hi",
    "परीक्षा कब शुरू होगी?": "hi",
    "वसतिगृहाचे शुल्क किती आहे?": "mr",
    "बी.टेक साठी शिक्षण शुल्क काय आहे?": "mr",
    "परीक्षा कधी सुरू होणार आहे?": "mr",
    "hostel ki fees kitni hai": "hinglish",
    "btech ka tuition fee kya hai?": "hinglish",
    "exam kab shuru hoga?": "hinglish",
    "What is the hostel fee?": "en",
    "Is there a hostel for girls?": "en",
    "When is the convocation?": "en",
}


def test_language_detection():
    import language
    wrong = {q: language.detect(q) for q, want in LANGUAGE_PHRASINGS.items() if language.detect(q) != want}
    assert not wrong, wrong


def test_hinglish_first_search_is_in_english():
    import language
    words = language.english_keywords("hostel ki fees kitni hai", language.HINGLISH).lower()
    assert "hostel" in words and "fee" in words and "kitni" not in words, words
    hindi = language.english_keywords("बी.टेक लड़कियों की हॉस्टल फीस कितनी है?", language.HINDI)
    assert all(w in hindi for w in ("B.Tech", "girls", "hostel", "fee")), hindi
    out = with_env({"GENAI_API_KEY": None}, lambda: respond.answer("hostel ki fees kitni hai", use_agent=True))
    assert "hostel" in out["understood_as"].lower() and "fee" in out["understood_as"].lower(), out["understood_as"]
    assert any("Hinglish" in t["text"] for t in out["trace"]), out["trace"]


def test_numbers_in_a_hindi_answer_pass_the_verifier():
    import agent_loop
    import language
    line = language.instruction(language.HINDI)
    for text in ("लड़कियों की हॉस्टल फीस **Rs. 32,650** है [P1]।", "हॉस्टल फीस ३२६५० रुपये है [P1]।"):
        with FakeLLM([reply(text)]) as fake:
            out = agent_loop.run("What is the girls' hostel fee?", REPORT, api_key="k", instructions=[line])
        assert out["verification"]["verdict"] == "verified", (text, out["verification"])
    assert "Hindi" in fake.sent[0]["messages"][0]["content"] and "0-9" in line


def test_greetings_in_hindi_and_marathi():
    out = respond.answer("नमस्ते")
    assert out["mode"] == "direct (greeting)" and "VNIT" in out["answer"] and "नमस्ते" in out["answer"]
    out = respond.answer("धन्यवाद")
    assert out["mode"] == "direct (thanks)", out["mode"]


# ---------------------------------------------------------------------------
# Step 6: streaming
# ---------------------------------------------------------------------------

def stream_reply(text, tokens=100):
    """A Groq-style streamed reply: one data: line per word, usage at the end, [DONE]."""
    import re
    lines = ["data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
             for p in re.findall(r"\S+\s*", text)]
    lines.append("data: " + json.dumps({"choices": [], "x_groq": {"usage": {"total_tokens": tokens}}}))
    lines.append("data: [DONE]")
    return FakeResponse(200, lines=lines)


def _api():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from api import main
    return main


def _events(body: str):
    """[(event, data)] from an SSE body; comment lines as ("comment", text)."""
    out = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        if block.startswith(":"):
            out.append(("comment", block[1:].strip()))
            continue
        event = next(l[7:] for l in block.splitlines() if l.startswith("event: "))
        data = json.loads(next(l[6:] for l in block.splitlines() if l.startswith("data: ")))
        out.append((event, data))
    return out


QUESTION = "What is the hostel fee for first year B.Tech girls for Winter 2026?"
TOOL_ROUND = lambda: reply("1. Find the first year girls' hostel fee.",
                           [call("lookup_table", {"keywords": "girls hostel fee first year"})])


def test_stream_sends_steps_then_tokens_then_done_equal_to_ask():
    from fastapi.testclient import TestClient
    main = _api()
    client = TestClient(main.app)
    answer = "The hostel fee for first year girls is **Rs. 32,650** [P1]."
    flags = {"GENAI_API_KEY": "test-key", "AGENT_V2": "on", "CLARIFY": "off"}
    with FakeLLM([TOOL_ROUND(), reply(answer)]):
        plain = with_env(flags, lambda: client.post("/ask", json={"question": QUESTION}).json())
    with FakeLLM([TOOL_ROUND(), stream_reply(answer)]):
        body = with_env(flags, lambda: client.post("/ask/stream", json={"question": QUESTION}).text)
    events = _events(body)
    kinds = [e for e, _ in events]
    assert kinds[0] == "step" and kinds[-1] == "done" and "token" in kinds, kinds
    tool_at = next(i for i, (e, d) in enumerate(events) if e == "step" and d["step"] == "tool")
    assert tool_at < kinds.index("token"), kinds      # the lookup is shown before the answer streams
    assert all(d["step"] in ("answer", "verify") for e, d in events[kinds.index("token"):-1]
               if e == "step"), "only the answer's own steps come after the tokens"
    streamed = "".join(d for e, d in events if e == "token")
    done = events[-1][1]
    assert streamed.strip() in done["answer"] and "[P1]" not in streamed and "[1]" in streamed, streamed
    assert done == plain, {k: (done.get(k), plain.get(k)) for k in set(done) | set(plain) if done.get(k) != plain.get(k)}
    assert done["suggestions"] and all("fee" in s.lower() or "remission" in s.lower() or "mess" in s.lower()
                                       for s in done["suggestions"]), done["suggestions"]


def test_stream_keeps_the_question_limits():
    from fastapi.testclient import TestClient
    client = TestClient(_api().app)
    assert client.post("/ask/stream", json={"question": "x" * 501}).status_code == 400
    assert client.post("/ask/stream", json={"question": "  "}).status_code == 400


def test_stop_cancels_the_worker():
    import asyncio
    import queue
    import threading
    main = _api()
    events, cancel = queue.Queue(), threading.Event()
    events.put(("step", {"step": "search", "text": "Searched"}))
    seen = []

    async def gone():
        return len(seen) >= 1   # the page goes away after the first event

    async def collect():
        async for chunk in main.event_stream(events, cancel, gone, ping_seconds=0.05):
            seen.append(chunk)

    asyncio.run(collect())
    assert len(seen) == 1 and cancel.is_set()

    import agent_loop
    stopped = threading.Event()
    stopped.set()
    with FakeLLM([reply("**Rs. 32,650** [P1].")]):
        try:
            agent_loop.run("q", REPORT, api_key="k", emit=lambda e, d: None, cancel=stopped)
        except agent_loop.Cancelled:
            return
    raise AssertionError("a cancelled run should stop")


def test_stop_closes_the_llm_stream_mid_answer():
    import threading
    import agent_loop
    cancel = threading.Event()
    got = []

    def emit(event, data):
        if event == "token":
            got.append(data)
            cancel.set()      # Stop pressed after the first word

    with FakeLLM([stream_reply("one two three four five six seven")]):
        llm = planner._LLM("k", "https://example.invalid", "m")
        try:
            agent_loop.stream_text(llm, [{"role": "user", "content": "x"}],
                                   lambda text: emit("token", text), cancel)
        except agent_loop.Cancelled:
            pass
    assert got == ["one "], got


def test_ping_comment_while_waiting():
    import asyncio
    import queue
    import threading
    main = _api()
    events, cancel = queue.Queue(), threading.Event()
    threading.Timer(0.3, lambda: events.put(("done", {"answer": "ok"}))).start()
    chunks = []

    async def never():
        return False

    async def collect():
        async for chunk in main.event_stream(events, cancel, never, ping_seconds=0.1):
            chunks.append(chunk)

    asyncio.run(collect())
    assert any(c.startswith(": ping") for c in chunks) and chunks[-1].startswith("event: done"), chunks


def test_suggestions_follow_the_topic():
    fee = respond.suggestions({"mode": "agent v2 (m)", "intent": "fees", "question": "What is the M.Tech tuition fee?"})
    assert len(fee) == 3 and any("M.Tech" in s for s in fee), fee
    assert all(respond.suggestions({"mode": "agent", "intent": "placement", "question": "q"}))
    assert respond.suggestions({"mode": "clarify", "intent": "fees", "question": "q"}) == []
    same = respond.suggestions({"mode": "agent", "intent": "people", "question": "Who is the Registrar of VNIT Nagpur?"})
    assert "Who is the Registrar of VNIT Nagpur?" not in same, same


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
