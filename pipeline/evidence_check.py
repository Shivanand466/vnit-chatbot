"""
Is the answer in the evidence the agent starts from? No key, no LLM.

`chunk_ranks.py` measures `agent.answer`, the first search. But the agent's
first prompt holds more than that: `respond.answer` reads follow-ups, fills the
chat's profile, and adds the corrective step's passages (`corrective_passages`)
before the planner sees anything. A fix that works there -- the corrective
passages that brought the placement figures in (EXPERIMENTS-LOG §20c) -- is
invisible to chunk_ranks.

This runs `respond.answer` for real with the planner replaced by a stand-in
that records what it was given (the first-search passages, exactly as
`planner.run` takes them with `generate.select_passages`, plus the corrective
ones) and answers nothing. A question counts when the pattern
`check_answers.py` looks for in the final answer is in that evidence.

    python evidence_check.py             # summary + the misses
    python evidence_check.py --verbose   # every question
    python evidence_check.py --only holi # questions whose name contains "holi"
"""
import argparse
import os
import re
import sys

import generate
import agent_loop
import planner
import respond
from check_answers import CHECKS, CLARIFY_CHECKS, CONVERSATIONS, NOT_FOUND
from chunk_ranks import passage_text


def cases():
    """(name, question, history, profile, pattern) for every case with an answer to find."""
    for name, question, must, _ in CHECKS:
        if must and NOT_FOUND not in must:
            yield name, question, [], None, must[0]
    for name, turns, must, _ in CONVERSATIONS:
        yield name, turns[-1], turns[:-1], None, must[0]
    for name, question, profile, expect in CLARIFY_CHECKS:
        if expect.get("must"):
            yield name, question, [], profile, expect["must"][0]


def evidence_for(question: str, history=None, profile=None):
    """(first-search passages, corrective passages) the planner would be given,
    as lists of texts; None when respond.answer did not get as far (it asked
    back, or needed no search)."""
    seen = {}

    def stand_in(q, report, extra=None, search_grade=None, **_):
        seen["first"] = [text for _r, text in generate.select_passages(report)]
        seen["extra"] = [text for _r, text in extra or []]
        return {"answer": "", "sources": [], "mode": "agent (evidence check)", "trace": [],
                "verification": None, "usage": None}

    # Agent v2 (agent_loop.run) is handed the same passages; both are stood in for.
    real, real_v2 = planner.run, agent_loop.run
    planner.run = agent_loop.run = stand_in
    try:
        respond.answer(question, history=history, profile=profile, use_agent=True)
    finally:
        planner.run, agent_loop.run = real, real_v2
    return (seen["first"], seen["extra"]) if seen else None


def where(pattern: str, evidence):
    """"first", "corrective", or None: where the answer is in the evidence."""
    if evidence is None:
        return None
    for origin, texts in zip(("first", "corrective"), evidence):
        if any(re.search(pattern, passage_text(t), re.I) for t in texts):
            return origin
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    os.environ.pop("GENAI_API_KEY", None)  # nothing here may reach an LLM

    rows = []
    for name, question, history, profile, pattern in cases():
        if args.only not in name:
            continue
        evidence = evidence_for(question, history, profile)
        found = where(pattern, evidence)
        rows.append((name, found, evidence))
        if args.verbose:
            note = ("asked back / no search" if evidence is None else
                    f"{found or 'missing':<10} ({len(evidence[0])} first, {len(evidence[1])} corrective)")
            print(f"  {note:<45} {name}")
            sys.stdout.flush()

    facts = [r for r in rows if r[0] in {c[0] for c in CHECKS}]
    others = [r for r in rows if r not in facts]
    for label, group in (("fact questions", facts), ("conversations and profile cases", others)):
        if group:
            hits = [r for r in group if r[1]]
            print(f"Answer in the evidence, {label}: {len(hits)}/{len(group)} "
                  f"({sum(1 for r in hits if r[1] == 'corrective')} only through the corrective step)")
    misses = [n for n, found, _ in rows if not found]
    if misses:
        print(f"\nNot in the evidence ({len(misses)}): {', '.join(misses)}")
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
