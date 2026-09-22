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
]

RESULTS_PATH = Path(__file__).parent.parent / "data" / "processed" / "answer_check.json"


def run(only: str = "", pause: float = 20.0):
    results = []
    checks = [c for c in CHECKS if only in c[0]]
    for i, (name, question, must, must_not) in enumerate(checks):
        if i:
            time.sleep(pause)
        out = generate.compose_answer(agent.answer(question))
        answer = out["answer"]
        missing = [p for p in must if not re.search(p, answer, re.I)]
        forbidden = [p for p in must_not if re.search(p, answer, re.I)]
        llm = out["mode"].startswith("llm")
        ok = llm and not missing and not forbidden
        results.append({"name": name, "question": question, "pass": ok, "mode": out["mode"],
                        "missing": missing, "forbidden": forbidden, "answer": answer,
                        "sources": [s["url"] for s in out["sources"]]})
        flag = "PASS" if ok else "FAIL"
        why = "" if ok else (" (not LLM mode)" if not llm else "") + \
            (f" missing {missing}" if missing else "") + (f" contains {forbidden}" if forbidden else "")
        print(f"[{flag}] {name}{why}")
        sys.stdout.flush()

    passed = sum(r["pass"] for r in results)
    print(f"\nAnswer check: {passed}/{len(results)} passed")
    RESULTS_PATH.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Full answers saved to {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--pause", type=float, default=20.0)
    a = ap.parse_args()
    run(a.only, a.pause)
