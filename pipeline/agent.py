"""
Phase 2: a thin agentic layer on top of plain retrieval (query.py).

What it adds, without needing an LLM (still no free API key wired in):
1. Query decomposition -- split a multi-part question into sub-questions
   and retrieve for each separately, instead of one blended (and worse)
   search over the whole compound question.
2. Recency-aware ranking -- when two retrieved chunks cover the same
   source page/topic, prefer the one from the more recent crawl. Today
   every page was crawled on the same day so this mostly no-ops; it's
   the hook the scheduled re-crawl (Data & Knowledge Pipeline, plan doc)
   plugs into once we have more than one snapshot in time.
3. Conflict flagging -- a crude signal: if the top two chunks for the
   same sub-question come from different source pages and don't share
   much vocabulary, flag it as "check for conflicting sources" rather
   than silently picking one.

Still missing: turning these cited passages into a single composed
natural-language answer -- that needs an LLM, which is the open
free-tier-vs-local decision in the plan doc's Next Steps.
"""
import re

from query import retrieve as _retrieve_all


SPLIT_PATTERN = re.compile(r"\s+\band\b\s+|\s*;\s*", re.IGNORECASE)
QUESTION_HINTS = re.compile(
    r"\b(what|when|who|how|which|where|why|does|is|are|can|do)\b", re.IGNORECASE
)

# FIX (2026-09-21, see REPORT2.md/REPORT3.md): a compound question like
# "Tell me about the 5G lab and when was it announced" splits cleanly into
# two parts, but the second one ("when was it announced") only makes sense
# with the first part's subject in view -- split apart, retrieval searches
# for that sentence alone, finds nothing about a 5G lab, and returns an
# unrelated page (REPORT3.md's confirmed real-world example: pulled a
# convocation-instructions page instead). PRONOUN_PATTERN below catches a
# bare referring pronoun in a later sub-question so decompose() can
# substitute in the real subject.
PRONOUN_PATTERN = re.compile(r"\b(it|this|that|they|them|its|their)\b", re.IGNORECASE)
LEADING_PHRASE_PATTERN = re.compile(
    r"^(tell me about|what is|what are|what's|when was|when is|when did|"
    r"where is|where can i find|who is|who are|explain|describe|"
    r"give me information (on|about)|information (on|about))\s+",
    re.IGNORECASE,
)


def _extract_topic(text: str) -> str:
    """Heuristic: strip a leading question/imperative phrase off a
    sub-question, leaving (hopefully) a bare noun phrase suitable for
    substituting into a later sub-question's dangling pronoun. Falls back to
    the original text if nothing recognizable was stripped."""
    stripped = LEADING_PHRASE_PATTERN.sub("", text.strip())
    return stripped.strip() or text.strip()


def decompose(question: str):
    """Split a compound question into sub-questions when it plausibly has more
    than one distinct ask. Falls back to the whole question if splitting
    doesn't produce two sensible parts."""
    question = question.strip().rstrip("?")
    parts = [p.strip() for p in SPLIT_PATTERN.split(question) if p.strip()]
    if len(parts) < 2:
        return [question]

    sub_questions = []
    for part in parts:
        # Only keep a fragment as its own sub-question if it looks like one
        # (has enough words and reads like a question/claim on its own).
        if len(part.split()) >= 3:
            sub_questions.append(part)
    if len(sub_questions) < 2:
        return [question]

    # Resolve dangling pronouns in later sub-questions against the topic of
    # whichever sub-question came before them.
    resolved = [sub_questions[0]]
    topic = _extract_topic(sub_questions[0])
    for part in sub_questions[1:]:
        if PRONOUN_PATTERN.search(part):
            part = PRONOUN_PATTERN.sub(lambda m: topic, part, count=1)
        resolved.append(part)
        topic = _extract_topic(part)
    return resolved


def _shared_vocab_ratio(text_a: str, text_b: str) -> float:
    words_a = set(w.lower() for w in re.findall(r"[a-zA-Z]{4,}", text_a))
    words_b = set(w.lower() for w in re.findall(r"[a-zA-Z]{4,}", text_b))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def retrieve_for_subquestion(sub_question: str, k: int = 3):
    results = _retrieve_all(sub_question, k=k)

    # No re-sorting here: retrieve() returns results in final (reranked) order,
    # and "score" is only the raw embedding similarity -- sorting by it would
    # undo the reranker. Dates are passed to the LLM instead (generate.py),
    # which is told to prefer the most recent document when sources disagree.

    conflict_flag = None
    if len(results) >= 2 and results[0]["source_url"] != results[1]["source_url"]:
        overlap = _shared_vocab_ratio(results[0]["text"], results[1]["text"])
        if overlap < 0.15 and results[1]["score"] > 0.15:
            conflict_flag = (
                f"Top two matches come from different pages "
                f"({results[0]['title']} vs {results[1]['title']}) with little shared "
                f"content -- verify both before trusting one over the other."
            )

    return results, conflict_flag


def answer(question: str, k: int = 5):
    sub_questions = decompose(question)
    report = {"question": question, "sub_questions": []}
    for sq in sub_questions:
        results, conflict = retrieve_for_subquestion(sq, k=k)
        report["sub_questions"].append({
            "sub_question": sq,
            "results": results,
            "conflict_warning": conflict,
        })

    # FIX (2026-09-21, see REPORT5.md): splitting a compound question can lose
    # shared context that only the *undivided* question carries. Measured
    # example: "How many students got placed in 2025-26 and how many
    # companies came?" splits into two halves, neither of which retrieves the
    # actual placements chunk (it needs "placement" together with the
    # numbers) -- but with a real embeddings index, that chunk ranks 2nd for
    # the whole question. The pronoun-substitution fix from last round covers
    # "...and when was it announced"-style loss; this covers the case where
    # there's no pronoun to catch, just shared subject the split throws away.
    # Retrieving for the whole question too, and letting generate.py merge in
    # anything not already covered, is a strict superset -- it can only add
    # candidates, never remove ones the sub-questions already found.
    if len(sub_questions) > 1:
        report["whole_question_results"] = _retrieve_all(question, k=k)

    return report


def print_report(report):
    print(f"\nQ: {report['question']}")
    if len(report["sub_questions"]) > 1:
        print(f"  (decomposed into {len(report['sub_questions'])} sub-questions)")
    for sq in report["sub_questions"]:
        print(f"\n  -> {sq['sub_question']}")
        if sq["conflict_warning"]:
            print(f"     [!] {sq['conflict_warning']}")
        for r in sq["results"][:2]:
            print(f"     [score {r['score']:.3f}] {r['title']} — {r['source_url']}")
            snippet = r["text"][:200].replace("\n", " ")
            print(f"       {snippet}{'...' if len(r['text']) > 200 else ''}")


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "What is the fee for B.Tech and where can I find the hostel rules?"
    print_report(answer(q))
