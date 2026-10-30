"""
End-to-end answer check: asks the full chatbot (retrieval + LLM) real
questions and checks each answer for facts that were verified by hand in
the source pages/documents.

evaluate.py only checks whether the right *page* is retrieved; this checks
whether the final *answer* is right -- including questions the chatbot must
decline because the answer isn't in its data.

Every question goes through respond.answer, the same function the chat page
calls, so what is measured is what students get. Two pipelines can be
measured on the same questions:

    agent    the planner (planner.py): may search again, open a document,
             calculate; every answer verified -- what the chat page runs
    oneshot  one search, one LLM call (generate.py) -- the pipeline before
             the agent existed, kept as the fallback and as the baseline

Needs GENAI_API_KEY set (same as the API). Waits between questions to stay
under Groq's free-tier tokens-per-minute limit.

    python check_answers.py                     # all checks, agent pipeline
    python check_answers.py --pipeline oneshot  # the baseline
    python check_answers.py --only fee          # only checks whose name contains "fee"
    python check_answers.py --resume            # re-ask only what never reached the LLM
                                                # (e.g. the daily quota ran out mid-run)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import respond

# Widened 2026-10-30: the agent's refusals read "none of the provided documents
# contain ..." and "I couldn't find ...", which the narrower pattern marked as
# failures although each was a correct refusal (all four were read by hand).
NOT_FOUND = (r"(do(es)? not|doesn't|don't|no (information|details|mention)|"
             r"not (contain|mention|provide|cover|include|specif|state|available|list)|"
             r"none of the (provided |retrieved |available )?(\w+ )?(passages|documents|sources)|"
             r"no (passage|document|source)s? (provides?|contains?|mentions?|states?|gives?)|"
             r"couldn't find|could not find|unable to find)")

# name, question, patterns that must ALL appear, patterns that must NOT appear
CHECKS = [
    ("civil_intake", "How many undergraduate students does Civil Engineering enroll annually?", [r"\b120\b"], []),
    ("5g_announced", "Tell me about the 5G lab and when was it announced", [r"2023", r"\b27\b"], []),
    ("placements", "How many students got placed in 2025-26 and how many companies came?", [r"678", r"170"], []),
    ("chemical_spec", "What two specializations does Chemical Engineering offer?", [r"Chemical Technology"], []),
    ("electrical_mtech", "What specializations does the Electrical Engineering M.Tech offer?",
     [r"Integrated Power"], [r"Communication System"]),
    ("director", "Who is the current Director of VNIT?", [r"Prem\s*Lal\s*Patel"], []),
    ("dean_academic_email", "What is the email of the Dean (Academic)?", [r"deanacd@vnit\.ac\.in"], []),
    ("mech_established", "When was the Mechanical Engineering department established?", [r"1960"], []),
    ("registrar", "Who is the Registrar of VNIT Nagpur?", [r"Jagdale"], []),
    ("btech_fee_open", "What is the yearly tuition fee for B.Tech students in the OPEN category?",
     [r"1,?25,?000|125000|1\.25 lakh"], []),
    ("btech_fee_scst", "What tuition fee do SC/ST B.Tech students pay?",
     [r"\b0\b|nil|waived|exempt|no tuition|free"], [r"1,?25,?000 per|125000 per"]),
    ("kotak_scholarship", "How much money does the Kotak Kanya Scholarship give per year?",
     [r"1\.5\s*(lakh|L)|1,50,000|150,?000"], []),
    ("idfc_deadline", "What is the last date to apply for the IDFC FIRST Bank Engineering Scholarship?",
     [r"20(th)?\s+September,?\s+2026|September\s+20(th)?,?\s+2026|20[./-]0?9[./-]2026"], []),
    ("hostel_fee_first_year", "What is the hostel fee for first year B.Tech boys for the Winter 2026 session?",
     [r"32,?150"], []),
    ("classes_start_fy", "When do classes start for first year B.Tech students in Winter 2026?",
     [r"19(th)?\s*(Aug|August)|(Aug|August)\s*19"], []),
    ("endsem_fy", "When are the end semester exams for first year B.Tech in Winter 2026?",
     [r"\b7(th)?\b.{0,25}\b15(th)?\b"], []),
    ("unanswerable_1995", "Who won the VNIT cricket match against IIT Bombay in 1995?", [NOT_FOUND], []),
    ("unanswerable_wifi", "What is the hostel wifi password?", [NOT_FOUND], []),

    # Added 2026-10-03. Every fact below was read out of the source document by
    # hand before being written here; the document is named in the comment so
    # it can be checked again later. Written to spread across the kinds of
    # question a student actually asks, not only the ones already known to work.

    # HOSTEL FEES FOR FIRST YEAR GIRLS ADMITTED IN YEAR 2026-27 (Winter 2026: Rs 32,650)
    ("hostel_fee_girls", "What is the hostel fee for first year B.Tech girls for the Winter 2026 session?",
     [r"32,?650"], [r"32,?150"]),
    # cse_department.txt: "established in 1987"
    ("cse_established", "When was the Computer Science and Engineering department established?",
     [r"1987"], []),
    # ACADEMIC CALENDAR (Winter 2026): "Re-examination: 28 th to 31 st Dec 2026"
    ("reexam_dates", "When is the re-examination held in Winter 2026?",
     [r"\b28(th)?\b.{0,30}\b31(st)?\b"], []),
    # ACADEMIC CALENDAR (Winter 2026): "Convocation: 15 th Sep 2026"
    ("convocation", "When is the convocation in 2026?",
     [r"15(th)?\s*(Sept?|September)|(Sept?|September)\s*15"], []),
    # Winter 2026 Course Registration Schedule: Add/Drop processing by FA ends 17/08/2026
    ("adddrop_deadline", "What is the last date for processing Add and Drop requests by the faculty adviser in Winter 2026?",
     [r"17[./-]0?8[./-]2026|17(th)?\s+Aug"], []),
    # Anti-ragging affidavit: "Anti-Ragging Helpline at 1800180 5522"
    ("antiragging_helpline", "What is the national anti-ragging helpline number?",
     [r"1800\s?-?\s?180\s?-?\s?5522"], []),
    # Summer Term 2026 Notice: "Rs. 3000/- per course", max 3 theory courses
    ("summer_term_fee", "How much does one summer term course cost at VNIT?", [r"3,?000"], []),
    ("summer_term_max_courses", "How many courses can a student register for in the summer term?",
     [r"\b3\b|three"], []),
    # deans_2026.txt: Dean (Academic) is Dr. V. R. Kalamkar
    ("dean_academic_name", "Who is the Dean (Academic) at VNIT?", [r"Kalamkar"], []),
    # deans_2026.txt: Dean (Planning & Development) email
    ("dean_planning_email", "What is the email address of the Dean (Planning and Development)?",
     [r"deanp_f@vnit\.ac\.in"], []),
    # 2 Year Fee Estimate for Master of Science: tuition 15,000/year.
    # The category is deliberately not asked for: OCR mangled the sentence
    # introducing the second table ("Folr t orf VNIT, Nagpur."), so the
    # document no longer says in readable text that 15,000 is the OPEN rate --
    # only that SC/ST pay NIL. Asking the chatbot for a label its source lost
    # would be testing the scanner, not the chatbot.
    ("msc_tuition", "What is the yearly tuition fee for M.Sc students at VNIT?",
     [r"15,?000"], []),
    # 2 Year Fee Estimate for Master of Technology: OPEN/OBC/EWS tuition 70,000/year, SC/ST NIL
    ("mtech_tuition", "What is the yearly tuition fee for M.Tech students in the OPEN category?",
     [r"70,?000"], []),
    ("mtech_fee_scst", "What tuition fee do SC/ST M.Tech students pay?",
     [r"\b0\b|nil|waived|exempt|no tuition|free"], []),
    # 5 Year Fee Estimate for Bachelor of Architecture: tuition 125,000/year.
    # Same OCR damage to the category lead-in as msc_tuition above.
    ("barch_tuition", "What is the yearly tuition fee for B.Arch students at VNIT?",
     [r"1,?25,?000|125000"], []),
    # Hostel rules: electrical appliances prohibited except air coolers in summer
    ("hostel_appliances", "Can I keep a refrigerator in my hostel room at VNIT?",
     [r"prohibit|not allowed|not permitted|forbidden"], []),
    # ACADEMIC CALENDAR (Winter 2026): slot A mid sem on 1st Oct
    ("midsem_slot_a", "When is the mid semester exam for slot A in Winter 2026?",
     [r"1(st)?\s*(Oct|October)|(Oct|October)\s*1"], []),

    # More questions the chatbot must decline. The first two matter most: the
    # data holds a 2026-27 hostel fee and a 2024-25 placement report, so a
    # question about a year it has nothing for is the real test of whether it
    # answers from the right year instead of the nearest one.
    ("unanswerable_old_hostel_fee", "What was the hostel fee for first year B.Tech boys in 2015-16?",
     [NOT_FOUND], [r"32,?150", r"32,?650"]),
    ("unanswerable_director_salary", "What is the monthly salary of the VNIT Director?", [NOT_FOUND], []),
    ("unanswerable_bus_pass", "How much does a day scholar bus pass cost at VNIT?", [NOT_FOUND], []),
]

# Two-turn conversations, to check that a follow-up question is understood
# (followup.py). The last answer is what gets checked. Without the rewrite the
# second question retrieves nothing sensible, so these fail outright.
CONVERSATIONS = [
    ("conv_hostel_girls",
     ["What is the hostel fee for first year B.Tech boys for the Winter 2026 session?",
      "and for girls?"],
     [r"32,?650"], []),
    ("conv_mtech_tuition",
     ["What is the yearly tuition fee for B.Tech students in the OPEN category?",
      "what about M.Tech?"],
     [r"70,?000"], []),
]

# Clarify-or-assume cases (slots.py): name, question, profile the chat page
# sends, and what must happen. "clarify" names a value that must be among the
# choices offered; otherwise the answer is checked like any other, and it must
# not have been a clarifying question. The vague question needs no LLM.
CLARIFY_CHECKS = [
    ("clarify_hostel_vague", "What is the hostel fee?", {}, {"clarify": "btech"}),
    # HOSTEL FEES FOR FIRST YEAR GIRLS ADMITTED IN YEAR 2026-27 (Rs 32,650)
    ("clarify_then_answer", "What is the hostel fee for first year?",
     {"programme": "btech", "gender": "girls"}, {"must": [r"32,?650"]}),
    ("no_clarify_when_specific",
     "What is the hostel fee for first year B.Tech boys for the Winter 2026 session?", {},
     {"must": [r"32,?150"]}),
    ("no_clarify_director", "Who is the Director of VNIT?", {}, {"must": [r"Prem\s*Lal\s*Patel"]}),
]

# The hard subset, for measuring what each piece of the agent contributes
# (EXPERIMENTS-LOG ablations) at about a third of a full run's quota: the
# questions that failed or needed tools on 2026-10-30, the girls' hostel fee,
# two must-decline questions, both conversations and the clarify cases.
HARD = [
    "placements", "msc_tuition", "barch_tuition", "midsem_slot_a", "summer_term_fee",
    "hostel_fee_girls", "unanswerable_wifi", "unanswerable_old_hostel_fee",
    "conv_hostel_girls", "conv_mtech_tuition",
    "clarify_hostel_vague", "clarify_then_answer", "no_clarify_when_specific", "no_clarify_director",
]

PROCESSED = Path(__file__).parent.parent / "data" / "processed"
# The agent's results keep the old file name, since the agent is what the chat
# page runs; the baseline gets its own file so the two can be compared.
RESULTS_PATHS = {"agent": PROCESSED / "answer_check.json",
                 "oneshot": PROCESSED / "answer_check_oneshot.json"}


# The LLM writes typographic punctuation -- non-breaking hyphens (U+2011),
# en/em dashes, narrow no-break spaces between a number and its unit. A correct
# answer ("1800-180-5522" with U+2011 hyphens) was being marked wrong because
# the pattern's plain "-" could not match, so every answer is normalised to
# ASCII punctuation before the patterns are applied.
_PUNCT = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", "​": "",
    "‘": "'", "’": "'", "“": '"', "”": '"',
}


def normalise(text: str) -> str:
    for odd, plain in _PUNCT.items():
        text = text.replace(odd, plain)
    return text


# Answers carry citation markers ("[2]") pointing at their sources. They are
# removed before matching, so a marker can never satisfy a pattern like \b3\b.
_CITATION = re.compile(r"\[\d+\]")


def reached_llm(mode: str) -> bool:
    return mode.startswith(("llm", "agent"))


def _score_clarify(name, question, profile, expect, out, results):
    """Score a CLARIFY_CHECKS case: a clarifying question with the right choice, or a right answer."""
    if "clarify" in expect:
        offered = [c["value"] for c in (out.get("clarify") or {}).get("choices", [])]
        ok = out["mode"] == "clarify" and expect["clarify"] in offered
        record = {"name": name, "question": question, "pass": ok, "mode": out["mode"],
                  "missing": [] if ok else [f"clarify with {expect['clarify']}"], "forbidden": [],
                  "answer": out["answer"], "sources": [], "profile": profile, "choices": offered,
                  "verification": None, "usage": None, "seconds": out.get("seconds"),
                  "trace": [t["text"] for t in out.get("trace", [])]}
        results.append(record)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  (mode: {out['mode']}, choices: {offered})")
        sys.stdout.flush()
        return ok
    forbidden_mode = out["mode"] == "clarify"
    ok = _score(name, question, out, expect.get("must", []), expect.get("must_not", []), results,
                extra={"profile": profile})
    if forbidden_mode:
        results[-1]["pass"] = False
        results[-1]["forbidden"].append("asked a clarifying question")
        print(f"  -> FAIL: {name} asked a clarifying question instead of answering")
    return ok and not forbidden_mode


def _quota_failure(mode: str, trace_texts) -> bool:
    # The agent names the daily limit in its trace; the one-shot path only
    # reports "429" in its mode. With 30s between questions, a 429 that
    # survives the agent's own waiting is the daily limit in practice.
    return not reached_llm(mode) and ("429" in mode or any("daily allowance" in t for t in trace_texts))


def _daily_limit(out) -> bool:
    """True when this answer failed because the AI allowance is spent."""
    return _quota_failure(out["mode"], [t.get("text", "") for t in out.get("trace", [])])


def _daily_limit_hit(results) -> bool:
    last = results[-1]
    return not last["pass"] and _quota_failure(last["mode"], last.get("trace", []))


def _score(name, question, out, must, must_not, results, extra=None):
    answer = _CITATION.sub("", normalise(out["answer"]))
    missing = [p for p in must if not re.search(p, answer, re.I)]
    forbidden = [p for p in must_not if re.search(p, answer, re.I)]
    llm = reached_llm(out["mode"])
    ok = llm and not missing and not forbidden
    record = {"name": name, "question": question, "pass": ok, "mode": out["mode"],
              "missing": missing, "forbidden": forbidden, "answer": out["answer"],
              "sources": [s["url"] for s in out["sources"]],
              "verification": out.get("verification"), "usage": out.get("usage"),
              "seconds": out.get("seconds"),
              "trace": [t["text"] for t in out.get("trace", [])]}
    record.update(extra or {})
    results.append(record)
    flag = "PASS" if ok else "FAIL"
    why = "" if ok else (" (not LLM mode)" if not llm else "") + \
        (f" missing {missing}" if missing else "") + (f" contains {forbidden}" if forbidden else "")
    tools_used = (out.get("usage") or {}).get("tool_calls", 0)
    verdict = (out.get("verification") or {}).get("verdict", "-")
    print(f"[{flag}] {name}{why}  (tools: {tools_used}, check: {verdict})")
    sys.stdout.flush()
    return ok


def rescore(pipeline: str = "agent", config: str = ""):
    """Re-mark saved answers with the current patterns, without asking anything again.

    For when a pattern was wrong, not an answer: the answers stay exactly as
    the chatbot gave them, only the marking changes, and the change shows up
    in the patterns' history rather than as a hand-edited results file.
    """
    path = results_path(pipeline, config)
    saved = json.loads(path.read_text(encoding="utf-8"))
    patterns = {name: (must, must_not) for name, _q, must, must_not in CHECKS}
    patterns.update({name: (must, must_not) for name, _t, must, must_not in CONVERSATIONS})
    patterns.update({name: (e.get("must", []), e.get("must_not", []))
                     for name, _q, _p, e in CLARIFY_CHECKS if "clarify" not in e})
    changed = []
    for r in saved:
        if r["name"] not in patterns:
            continue  # a clarifying-question case: nothing in its answer to re-mark
        must, must_not = patterns[r["name"]]
        answer = _CITATION.sub("", normalise(r["answer"]))
        r["missing"] = [p for p in must if not re.search(p, answer, re.I)]
        r["forbidden"] = [p for p in must_not if re.search(p, answer, re.I)]
        ok = reached_llm(r["mode"]) and not r["missing"] and not r["forbidden"]
        if ok != r["pass"]:
            changed.append(f"{r['name']}: {'FAIL -> PASS' if ok else 'PASS -> FAIL'}")
        r["pass"] = ok
    path.write_text(json.dumps(saved, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(changed) or "No result changed.")
    print(f"\nAnswer check ({pipeline}, re-scored): {sum(r['pass'] for r in saved)}/{len(saved)} passed")


def results_path(pipeline: str = "agent", config: str = "") -> Path:
    """Where a run's answers are saved: per pipeline, or per named configuration."""
    return PROCESSED / f"answer_check_{config}.json" if config else RESULTS_PATHS[pipeline]


def complete(results, total: int) -> bool:
    """Every question asked and answered by the LLM (or, for a clarify case, asked back)."""
    return len(results) == total and all(reached_llm(r["mode"]) or r["mode"] == "clarify"
                                         for r in results)


def run(only: str = "", pause: float = 30.0, pipeline: str = "agent", resume: bool = False,
        subset: str = "", config: str = ""):
    use_agent = pipeline == "agent"
    path = results_path(pipeline, config)

    def wanted(name):
        return only in name and (subset != "hard" or name in HARD)

    # --resume keeps every saved result that reached the LLM and asks the rest
    # again: a run cut short by the daily quota can be finished the next day
    # without spending the quota twice on the questions already answered.
    kept = {}
    if resume and path.exists():
        kept = {r["name"]: r for r in json.loads(path.read_text(encoding="utf-8"))
                if reached_llm(r["mode"])}
        print(f"Resuming: keeping {len(kept)} saved result(s) that reached the LLM.")

    results = []
    asked = 0
    for name, question, must, must_not in [c for c in CHECKS if wanted(c[0])]:
        if name in kept:
            results.append(kept[name])
            continue
        if asked:
            time.sleep(pause)
        asked += 1
        out = _timed(respond.answer, question, use_agent=use_agent)
        _score(name, question, out, must, must_not, results)
        if _daily_limit(out):
            break

    # Conversations: the follow-up is resolved against the earlier questions,
    # exactly as the chat page sends them (`history`). The earlier turns are not
    # answered here -- the rewrite only reads the questions -- which saves a
    # whole answer's worth of quota per conversation.
    for name, turns, must, must_not in [c for c in CONVERSATIONS if wanted(c[0])]:
        if results and _daily_limit_hit(results):
            break
        if name in kept:
            results.append(kept[name])
            continue
        if asked:
            time.sleep(pause)
        asked += 1
        out = _timed(respond.answer, turns[-1], history=turns[:-1], use_agent=use_agent)
        _score(name, " | ".join(turns), out, must, must_not, results,
               extra={"understood_as": out.get("understood_as")})
        if _daily_limit(out):
            break

    for name, question, profile, expect in [c for c in CLARIFY_CHECKS if wanted(c[0])]:
        if results and _daily_limit_hit(results):
            break
        if name in kept:
            results.append(kept[name])
            continue
        if asked and "clarify" not in expect:
            time.sleep(pause)
        asked += 1
        out = _timed(respond.answer, question, profile=profile, use_agent=use_agent)
        _score_clarify(name, question, profile, expect, out, results)
        if _daily_limit(out):
            break

    # Once the daily allowance is spent, every further question would fail
    # the same way -- 35 of 39 did on 2026-10-30 -- so the run stops, the
    # failed question is dropped, and --resume asks it and the rest later.
    total = sum(len([c for c in cases if wanted(c[0])])
                for cases in (CHECKS, CONVERSATIONS, CLARIFY_CHECKS))
    if results and _daily_limit_hit(results):
        dropped = results.pop()
        print(f"\nSTOPPED: the free daily AI allowance is used up (at {dropped['name']}). "
              f"{total - len(results)} question(s) not asked yet; run again later with --resume.")

    passed = sum(r["pass"] for r in results)
    print(f"\nAnswer check ({pipeline}): {passed}/{len(results)} passed"
          + (f" ({total - len(results)} not asked yet)" if len(results) < total else ""))

    # What the agent did, for the report: how often it acted, and what the
    # verifier made of the answers.
    verdicts = {}
    for r in results:
        v = (r.get("verification") or {}).get("verdict", "not checked")
        verdicts[v] = verdicts.get(v, 0) + 1
    print("Verifier verdicts: " + ", ".join(f"{k} {n}" for k, n in sorted(verdicts.items())))
    usage = [r["usage"] for r in results if r.get("usage")]
    if usage:
        acted = sum(1 for u in usage if u.get("tool_calls"))
        tokens = sum(u.get("tokens", 0) for u in usage)
        print(f"Agent used tools on {acted}/{len(usage)} questions; "
              f"{tokens / len(usage):,.0f} tokens per question on average.")

    # A rate-limited run degrades quietly: every question after the limit is
    # hit falls back to extractive and is scored as a failure, which reads like
    # the chatbot got much worse. Say so instead.
    no_llm = [r["name"] for r in results if not reached_llm(r["mode"])]
    if no_llm:
        print(f"\nWARNING: {len(no_llm)} question(s) never reached the LLM, so their result "
              f"says nothing about answer quality:")
        print(f"  {', '.join(no_llm)}")
        reasons = {r["mode"] for r in results if not reached_llm(r["mode"])}
        for reason in reasons:
            print(f"  reason: {reason[:160]}")
        print("  If this is a 429, wait (or for the daily limit, until tomorrow) and run again "
              "with --resume.")
    # An --only run replaces just its own questions in the saved file; writing
    # the subset alone would throw away the last full run's other answers.
    saved = results
    if (only or subset) and not config and path.exists():
        fresh = {r["name"]: r for r in results}
        old = json.loads(path.read_text(encoding="utf-8"))
        saved = [fresh.pop(r["name"], r) for r in old] + list(fresh.values())
    path.write_text(json.dumps(saved, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Full answers saved to {path}")
    return results, total


def _timed(fn, *args, **kwargs):
    start = time.time()
    out = fn(*args, **kwargs)
    out["seconds"] = round(time.time() - start, 1)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    # 30s, not 20s: with 7 passages per question and a rewrite call for each
    # conversation turn, a 20s gap ran into Groq's free-tier per-minute token
    # limit part-way through a run, and every question after it fell back to
    # extractive -- which reads like a quality collapse but is only pacing.
    # The agent also paces itself (planner._Pacer), so a question that needs
    # tools waits for the allowance instead of failing.
    ap.add_argument("--pause", type=float, default=30.0)
    ap.add_argument("--pipeline", choices=sorted(RESULTS_PATHS), default="agent")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--set", default="", choices=["", "hard"], dest="subset",
                    help="hard: only the HARD questions (for the ablations)")
    ap.add_argument("--config", default="",
                    help="save to answer_check_<config>.json, e.g. one per ablation configuration")
    ap.add_argument("--rescore", action="store_true",
                    help="re-mark the saved answers with the current patterns; asks nothing")
    a = ap.parse_args()
    if a.rescore:
        rescore(a.pipeline, a.config)
    else:
        results, total = run(a.only, a.pause, a.pipeline, a.resume, a.subset, a.config)
        # Exit code 2 when the run is unfinished (daily quota, fallbacks), so a
        # script can wait and run it again with --resume.
        sys.exit(0 if complete(results, total) else 2)
