"""
Summarise the ratings collected by POST /feedback.

    python feedback_summary.py              # counts, plus the questions rated unhelpful
    python feedback_summary.py --all        # also list every question asked

Reads data/feedback/feedback.jsonl, which the chat page appends to when someone
presses thumbs up or down. That file is gitignored: it holds real students'
questions, so keep the numbers for the report and leave the file on the laptop.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

FEEDBACK_PATH = Path(__file__).parent.parent / "data" / "feedback" / "feedback.jsonl"


def load():
    if not FEEDBACK_PATH.exists():
        return []
    rows = []
    for line in FEEDBACK_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a half-written line from a crash shouldn't lose the rest
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="list every question asked")
    args = ap.parse_args()

    rows = load()
    if not rows:
        print(f"No ratings yet ({FEEDBACK_PATH} is empty or missing).")
        print("Ratings appear once someone presses the thumbs up/down buttons in the chat page.")
        return

    ratings = Counter(r.get("rating") for r in rows)
    up, down = ratings.get("up", 0), ratings.get("down", 0)
    days = sorted({r.get("at", "")[:10] for r in rows if r.get("at")})
    modes = Counter(r.get("mode", "").split(" (")[0] for r in rows)

    print(f"{len(rows)} ratings on {len(days)} day(s)"
          + (f" ({days[0]} to {days[-1]})" if days else ""))
    print(f"  helpful:     {up}" + (f"  ({up / len(rows):.0%})" if rows else ""))
    print(f"  not helpful: {down}")
    # Nested quotes inside an f-string only parse on Python 3.12+, and the
    # Docker image may run an older one, so this is built the plain way.
    mode_counts = ", ".join("{} x{}".format(m or "unknown", n) for m, n in modes.most_common())
    print(f"  answer mode: {mode_counts}")

    unhelpful = [r for r in rows if r.get("rating") == "down"]
    if unhelpful:
        print(f"\nRated not helpful ({len(unhelpful)}) -- worth reading before the demo:")
        for r in unhelpful:
            print(f"  - {r.get('question', '')[:100]}")
            if r.get("comment"):
                print(f"      comment: {r['comment'][:100]}")

    if args.all:
        print(f"\nAll {len(rows)} questions:")
        for r in rows:
            mark = "+" if r.get("rating") == "up" else "-"
            print(f"  {mark} {r.get('question', '')[:100]}")


if __name__ == "__main__":
    main()
