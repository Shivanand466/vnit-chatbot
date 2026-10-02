"""
Phase 3 groundwork: a small benchmark of real student questions with a known
correct source page, scored automatically. This is the accuracy-measurement
step the plan doc's Phase 3 calls for -- run whenever the corpus, chunking,
or ranking changes, to see if retrieval got better or worse.

This only scores retrieval (does the right page come back?), not the final
composed answer's wording -- that would need human judgment or an LLM judge,
neither of which is available inside Claude's sandbox right now.
"""
from query import retrieve

# Each case: a realistic question and the source_url substring that should
# appear in the top-k retrieved results. A tuple of substrings means any of
# them counts, which is needed now that documents are indexed: for some
# questions VNIT's own PDF answers better than the web page that links it, and
# the chatbot returning that PDF is the behaviour we want, not a miss.
#
# Only documents checked by hand for actually containing the answer are listed
# here (2026-10-02): the B.Tech fee estimate PDF states the per-year tuition
# (which the fees page does not), and the telephone directory holds the
# Registrar's office number (extension 1364 / 2226240). Everything else is
# left strict on purpose -- see EXPERIMENTS-LOG.md §11.
BENCHMARK = [
    ("When does B.Tech admission through JoSAA start reporting?", "admission"),
    ("How many students got placed in 2025-26 and how many companies came?", "tnp"),
    ("When was the CSE department established?", "engineering/cse"),
    ("Who do I contact for PhD admission queries?", "admission"),
    ("What is the academic calendar for winter 2026?", "academic-event-calendar"),
    ("How many boys' and girls' hostels does VNIT have?", "hostel"),
    ("What scholarships are available for girl students?", "notice"),
    ("What is the fee estimate for B.Tech?", ("fees", "1YwaPEqSM2OtnfmSd_N5W3ESgaIB_3Flv")),
    ("When was the Mechanical Engineering department established?", "engineering/mech"),
    ("When did VNIT get Institute of National Importance status?", "history"),
    ("What specializations does the Electrical Engineering M.Tech offer?", "engineering/electrical"),
    ("When was the Electronics and Communication department established?", "engineering/ece"),
    ("How many undergraduate students does Civil Engineering enroll annually?", "engineering/civil"),
    ("What two specializations does Chemical Engineering offer?", "engineering/chemical"),
    ("When was the Architecture department established?", "arch"),
    ("Who is the current Director of VNIT?", "director"),
    ("What are the library's operating hours on Sunday?", "library"),
    ("Who is the RTI Central Public Information Officer?", "rti-officer"),
    ("What is the phone number for the Registrar's Office?",
     ("contact-us", "10vMEaTpNvk2HLfYn9Z3fNixg51RV6ISs")),
]


def run(k: int = 3):
    hits = 0
    misses = []
    for question, expected in BENCHMARK:
        accepted = (expected,) if isinstance(expected, str) else expected
        results = retrieve(question, k=k)
        matched = any(a in r["source_url"] for r in results for a in accepted)
        if matched:
            hits += 1
        else:
            top = results[0] if results else None
            misses.append((question, " or ".join(accepted), top["source_url"] if top else None))

    total = len(BENCHMARK)
    print(f"Retrieval hit-rate (top-{k}): {hits}/{total} = {hits/total:.0%}\n")
    if misses:
        print("Misses:")
        for q, expected, got in misses:
            print(f"  Q: {q}\n    expected URL containing '{expected}', top result was: {got}")
    return hits, total


if __name__ == "__main__":
    run()
