"""
Retrieval check at the level that actually matters for answers: for each
question, at what rank does the first chunk containing the known answer
appear? (evaluate.py only checks the page; an answer is only possible if the
answer-bearing chunk is in the top few that reach the LLM.)

No LLM needed, so it's fast and free to run after any retrieval change.
Questions are passed through agent.decompose() so they're retrieved exactly
the way the chatbot retrieves them.
"""
import re
import sys

from agent import decompose, retrieve_for_subquestion

# question, regex that the answer-bearing chunk must match
FACTS = [
    ("Who is the Registrar of VNIT Nagpur?", r"Jagdale"),
    ("How many undergraduate students does Civil Engineering enroll annually?", r"intake of 120"),
    ("When was the 5G lab announced?", r"October 27, 2023"),
    ("How many students got placed in 2025-26?", r"678 students"),
    ("What specializations does the Electrical Engineering M.Tech offer?", r"Integrated Power"),
    ("When was the Mechanical Engineering department established?", r"inception of the institute \(1960\)"),
    ("What two specializations does Chemical Engineering offer?", r"Chemical Technology"),
    ("Who is the current Director of VNIT?", r"Prem Lal Patel"),
    ("What is the email of the Dean (Academic)?", r"deanacd@vnit\.ac\.in"),
    ("What is the phone number for the Registrar's Office?", r"Registrar Office\s*Contact No:\s*0712-2801359"),
    ("When did VNIT get Institute of National Importance status?", r"National Importance"),
    ("What is the yearly tuition fee for B.Tech students in the OPEN category?", r"OPEN.{0,120}Tuition Fee.{0,40}125000"),
    ("What tuition fee do SC/ST B.Tech students pay?", r"SC/ ?ST.{0,120}Tuition Fee — First Year: 0"),
    ("How much money does the Kotak Kanya Scholarship give per year?", r"1\.5 Lakhs Per Year"),
    ("What is the last date to apply for the IDFC FIRST Bank Engineering Scholarship?", r"20 September 2026"),
    ("What is the hostel fee for first year B.Tech boys for the Winter 2026 session?", r"Winter 2026 is Rs\. ?32150"),
    ("When do classes start for first year B.Tech students in Winter 2026?", r"Commencement of Classes: 19 th Aug 2026"),
    ("When are the end semester exams for first year B.Tech in Winter 2026?", r"End semester examination: 7 th Dec to 15 th Dec 2026"),
]


def rank_of(question, pattern, k=20):
    q = decompose(question)[0]
    results, _ = retrieve_for_subquestion(q, k=k)  # exactly the chatbot's retrieval path
    for i, r in enumerate(results, 1):
        if re.search(pattern, r["text"], re.S):
            return i
    return None


def main():
    in_top3 = 0
    for q, pat in FACTS:
        r = rank_of(q, pat)
        in_top3 += r is not None and r <= 3
        print(f"  rank {str(r) if r else '>20':>3}  {q}")
    print(f"\nAnswer-bearing chunk in top 3: {in_top3}/{len(FACTS)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
