"""
Retrieval benchmark that runs the chatbot's own path, without the LLM.

Why another one: `evaluate.py` calls `query.retrieve` directly and
`fact_ranks.py` calls `retrieve_for_subquestion` directly, so neither ever ran
`agent.answer` -- the function the API actually calls. A bug in `decompose`
(it stripped the question mark, which changed the cross-encoder's ranking
enough to lose the right document) was invisible to both.

This asks every answerable question from `check_answers.py` through
`agent.answer`, and reports how far down the results the answer-bearing
passage sits. The expected pattern is the same one `check_answers.py` looks
for in the final answer, so the two stay in step: if the passage is not
retrieved, no LLM can answer from it.

Needs no API key and costs nothing, so it is the right tool for tuning
retrieval -- and the one to run when the LLM's free quota is spent.

    python chunk_ranks.py            # summary + the misses
    python chunk_ranks.py --verbose  # every question's rank
"""
import argparse
import re
import sys

import agent
from check_answers import CHECKS, NOT_FOUND

# How many results agent.answer is asked for, and the cut-offs reported.
K = 12
WINDOW = 7  # passages generate.py may send to the LLM per sub-question


def cases():
    """The answerable checks: (name, question, pattern that the passage must match)."""
    for name, question, must, _must_not in CHECKS:
        if not must or NOT_FOUND in must:
            continue  # "must decline" questions have no answer-bearing passage
        yield name, question, must[0]


def passage_text(text: str) -> str:
    """Chunk text with PDF quirks smoothed out before matching.

    Scanned VNIT documents write ordinals with a space ("19 th Aug", "31 st
    Dec"), so a pattern written for an answer ("19th August") would not match
    the passage that actually holds the fact, and the question would be
    reported as a retrieval miss when retrieval had worked.
    """
    return re.sub(r"(\d)\s+(st|nd|rd|th)\b", r"\1\2", text, flags=re.I)


def rank_of(question: str, pattern: str):
    """1-based position of the first retrieved passage matching `pattern`, or None."""
    report = agent.answer(question, k=K)
    seen = []
    for sq in report["sub_questions"]:
        for r in sq["results"]:
            key = (r["source_url"], r["text"][:60])
            if key not in seen:
                seen.append(key)
                if re.search(pattern, passage_text(r["text"]), re.I):
                    return len(seen), r["title"]
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    rows = []
    for name, question, pattern in cases():
        rank, title = rank_of(question, pattern)
        rows.append((name, rank, title))
        if args.verbose:
            where = f"rank {rank:>2}  {title[:50]}" if rank else f"not in top {K}"
            print(f"  {where:<62} {name}")
            sys.stdout.flush()

    found = [r for _, r, _ in rows if r]
    in_window = [r for r in found if r <= WINDOW]
    in_three = [r for r in found if r <= 3]
    print(f"\nAnswer passage within top {WINDOW} (what the LLM sees): "
          f"{len(in_window)}/{len(rows)}")
    print(f"Answer passage within top 3:                      {len(in_three)}/{len(rows)}")
    print(f"Answer passage anywhere in top {K}:                {len(found)}/{len(rows)}")

    misses = [(n, r) for n, r, _ in rows if not r or r > WINDOW]
    if misses:
        print(f"\nNot reaching the LLM ({len(misses)}):")
        for name, rank in misses:
            print(f"  {name}: {'rank ' + str(rank) if rank else 'not in top ' + str(K)}")
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
