"""
Measure what grader.py's thresholds should be, instead of guessing them.

For every answerable question in check_answers.py, prints the first search's
best cross-encoder score (`top`), the share of the question's key words found
in the top three passages (`coverage`), whether the answer-bearing passage was
among the 7 sent to the LLM (from chunk_ranks.py), and the grade the current
thresholds give. The must-decline questions follow, which should never grade
`correct`. No API key needed.

    python grade_calibration.py

The thresholds are right when every question whose answer passage was missed
grades as not `correct`, while as many hits as possible grade `correct`.
"""
import sys

import agent
import grader
from check_answers import CHECKS, NOT_FOUND
from chunk_ranks import WINDOW, cases, rank_of


def row(name, question, hit):
    report = agent.answer(question, k=7)
    g = grader.grade(question, report)
    top = "-" if g["top"] is None else f"{g['top']:.1f}"
    hit_text = {True: "hit", False: "MISS", None: "decline"}[hit]
    print(f"| {name} | {top} | {g['coverage']:.2f} | {hit_text} | {g['grade']} |")
    sys.stdout.flush()
    return g, hit


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Thresholds: HIGH={grader.HIGH}, LOW={grader.LOW}, COVER={grader.COVER}\n")
    print("| question | top | coverage | answer passage in top 7 | grade |")
    print("|---|---|---|---|---|")
    rows = []
    for name, question, pattern in cases():
        rank, _title = rank_of(question, pattern)
        rows.append(row(name, question, rank is not None and rank <= WINDOW))
    for name, question, must, _ in CHECKS:
        if NOT_FOUND in must:
            rows.append(row(name, question, None))

    misses = [g for g, hit in rows if hit is False]
    hits = [g for g, hit in rows if hit is True]
    declines = [g for g, hit in rows if hit is None]
    print(f"\nMisses graded not correct: {sum(g['grade'] != 'correct' for g in misses)}/{len(misses)}")
    print(f"Hits graded correct:       {sum(g['grade'] == 'correct' for g in hits)}/{len(hits)}")
    print(f"Must-decline not correct:  {sum(g['grade'] != 'correct' for g in declines)}/{len(declines)}")


if __name__ == "__main__":
    main()
