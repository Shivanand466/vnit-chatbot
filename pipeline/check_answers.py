"""
End-to-end answer check: asks the full chatbot (retrieval + LLM) real
questions and checks each answer for facts that were verified by hand in
the source pages/documents.

evaluate.py only checks whether the right *page* is retrieved; this checks
whether the final *answer* is right -- including questions the chatbot must
decline because the answer isn't in its data.

Needs GENAI_API_KEY set (same as the API). Waits between questions to stay
under Groq's free-tier tokens-per-minute limit.

    python check_answers.py            # all checks
    python check_answers.py --only fee # only checks whose name contains "fee"
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import agent
import followup
import generate

NOT_FOUND = r"(do(es)? not|doesn't|don't|no (information|details|mention)|not (contain|mention|provide|cover|include|specif|state|available|list))"

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

RESULTS_PATH = Path(__file__).parent.parent / "data" / "processed" / "answer_check.json"


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


def _score(name, question, out, must, must_not, results, extra=None):
    answer = normalise(out["answer"])
    missing = [p for p in must if not re.search(p, answer, re.I)]
    forbidden = [p for p in must_not if re.search(p, answer, re.I)]
    llm = out["mode"].startswith("llm")
    ok = llm and not missing and not forbidden
    record = {"name": name, "question": question, "pass": ok, "mode": out["mode"],
              "missing": missing, "forbidden": forbidden, "answer": out["answer"],
              "sources": [s["url"] for s in out["sources"]]}
    record.update(extra or {})
    results.append(record)
    flag = "PASS" if ok else "FAIL"
    why = "" if ok else (" (not LLM mode)" if not llm else "") + \
        (f" missing {missing}" if missing else "") + (f" contains {forbidden}" if forbidden else "")
    print(f"[{flag}] {name}{why}")
    sys.stdout.flush()
    return ok


def run(only: str = "", pause: float = 30.0):
    results = []
    checks = [c for c in CHECKS if only in c[0]]
    for i, (name, question, must, must_not) in enumerate(checks):
        if i:
            time.sleep(pause)
        out = generate.compose_answer(agent.answer(question))
        _score(name, question, out, must, must_not, results)

    # Conversations: ask the earlier turns for context, then check the answer to
    # the follow-up, which is resolved the same way the API resolves it.
    for name, turns, must, must_not in [c for c in CONVERSATIONS if only in c[0]]:
        time.sleep(pause)
        history = []
        for turn in turns[:-1]:
            searched, _ = followup.resolve(turn, history)
            generate.compose_answer(agent.answer(searched))
            history.append(searched)
            time.sleep(pause)
        last = turns[-1]
        searched, note = followup.resolve(last, history)
        out = generate.compose_answer(agent.answer(searched))
        _score(name, " | ".join(turns), out, must, must_not, results,
               extra={"understood_as": searched, "rewrite": note})

    passed = sum(r["pass"] for r in results)
    print(f"\nAnswer check: {passed}/{len(results)} passed")

    # A rate-limited run degrades quietly: every question after the limit is
    # hit falls back to extractive and is scored as a failure, which reads like
    # the chatbot got much worse. Say so instead.
    no_llm = [r["name"] for r in results if not r["mode"].startswith("llm")]
    if no_llm:
        print(f"\nWARNING: {len(no_llm)} question(s) never reached the LLM, so their result "
              f"says nothing about answer quality:")
        print(f"  {', '.join(no_llm)}")
        reasons = {r["mode"] for r in results if not r["mode"].startswith("llm")}
        for reason in reasons:
            print(f"  reason: {reason[:160]}")
        print("  If this is a 429, re-run with a longer --pause (default 30s).")
    RESULTS_PATH.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Full answers saved to {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    # 30s, not 20s: with 7 passages per question and a rewrite call for each
    # conversation turn, a 20s gap ran into Groq's free-tier per-minute token
    # limit part-way through a run, and every question after it fell back to
    # extractive -- which reads like a quality collapse but is only pacing.
    ap.add_argument("--pause", type=float, default=30.0)
    a = ap.parse_args()
    run(a.only, a.pause)
