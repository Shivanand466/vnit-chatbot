"""
Agent v2's results and cost, from the saved answer-check runs (no LLM calls).

    python v2_table.py                       # the dev-model runs of Runbook 11
    python v2_table.py agent_v2 agent_v1     # any answer_check_<config>.json files

For each run: how many answers passed, and per question the average tokens,
seconds, tool calls and (v2) rounds. A multi-turn case counts all its turns.
Questions that never reached the model (the daily allowance ran out) are left
out of the averages, as check_answers.py leaves them out of the score.
"""
import json
import sys
from pathlib import Path

import check_answers

DEFAULT = ["agent_v2_dev", "agent_v2_dev_regression", "agent_v1_dev_regression"]


def summary(config: str):
    path = check_answers.results_path("agent", config)
    if not path.exists():
        return None
    results = [r for r in json.loads(path.read_text(encoding="utf-8")) if check_answers.answered(r)]
    usage = []
    for r in results:
        u = dict(r.get("usage") or {})
        if r.get("all_turns"):
            u.update({k: r["all_turns"][k] for k in ("tokens", "tool_calls", "llm_calls")})
            u["seconds"] = r["all_turns"]["seconds"]
        else:
            u["seconds"] = r.get("seconds") or 0
        if r["mode"] != "clarify":
            usage.append(u)

    def average(key):
        values = [u.get(key) or 0 for u in usage]
        return sum(values) / len(values) if values else 0

    return {"config": config, "asked": len(results), "passed": sum(r["pass"] for r in results),
            "tokens": average("tokens"), "seconds": average("seconds"),
            "tool_calls": average("tool_calls"), "steps": average("steps"),
            "failed": [r["name"] for r in results if not r["pass"]]}


def main(configs):
    sys.stdout.reconfigure(encoding="utf-8")
    print("| Run | Passed | Avg tokens | Avg seconds | Avg tool calls | Avg rounds |")
    print("|---|---|---|---|---|---|")
    rows = []
    for config in configs:
        s = summary(config)
        if s is None:
            print(f"| {config} | not run | | | | |")
            continue
        rows.append(s)
        print(f"| {config} | {s['passed']}/{s['asked']} | {s['tokens']:,.0f} | {s['seconds']:.0f} | "
              f"{s['tool_calls']:.1f} | {s['steps']:.1f} |")
    for s in rows:
        if s["failed"]:
            print(f"\n{s['config']} failed: {', '.join(s['failed'])}")


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
