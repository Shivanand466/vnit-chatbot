"""
What each piece of the agent contributes, measured: one table from the ablation runs.

The Agent-Orchestrated Adaptive RAG paper measured reflection *lowering*
overall scores and multiplying latency six times, so adding a piece is not
evidence that it helps. Each configuration below answers the HARD questions of
check_answers.py with one more piece switched on, and this reads their results
files and prints one markdown table: score, must-decline questions refused,
average tokens, seconds and tool calls, how often the corrective gate fired,
and how many questions were asked back.

    python check_answers.py --set hard --config no_tools ...   (see EXPERIMENTS-LOG §26)
    python ablation_table.py

The one-shot row is read from the full one-shot run (answer_check_oneshot.json),
restricted to the same questions: the one-shot pipeline has no pieces to switch.
"""
import json
import sys

from check_answers import HARD, PROCESSED, answered

# (row label, results file, environment switches used)
CONFIGS = [
    ("one-shot", "answer_check_oneshot.json", "--pipeline oneshot"),
    ("agent, no tools", "answer_check_no_tools.json",
     "AGENT_TOOLS=off CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off"),
    ("agent (30 Oct)", "answer_check_agent_30oct.json", "CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off"),
    ("+ CRAG gate", "answer_check_crag.json", "CLARIFY=off LOOKUP_TABLE=off"),
    ("+ clarify", "answer_check_clarify.json", "LOOKUP_TABLE=off"),
    ("full", "answer_check_full_hard.json", "none"),
    # Agent v2 (Runbook 11): its hard questions, taken from its full 105-case
    # run (`check_answers.py --config agent_v2`). On the agent-v2 branch the
    # rows above are v1, which is AGENT_V2=off there.
    ("agent v2", "answer_check_agent_v2.json", "AGENT_V2=on"),
]


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def row(label, filename, switches):
    path = PROCESSED / filename
    if not path.exists():
        return f"| {label} | not run yet | | | | | | | `{switches}` |"
    results = [r for r in json.loads(path.read_text(encoding="utf-8")) if r["name"] in HARD]
    counted = [r for r in results if answered(r)]
    declines = [r for r in counted if r["name"].startswith("unanswerable_")]
    usage = [r.get("usage") or {} for r in counted]
    tokens = _mean([u.get("tokens") for u in usage])
    seconds = _mean([r.get("seconds") for r in counted])
    tool_calls = _mean([u.get("tool_calls") for u in usage if u])
    gate = sum(any("first search looked weak" in t for t in r.get("trace", [])) for r in counted)
    asked_back = sum(r["mode"] == "clarify" for r in counted)
    score = f"{sum(r['pass'] for r in counted)}/{len(counted)}"
    if len(counted) < len(HARD):
        score += f" ({len(HARD) - len(counted)} not answered yet)"
    fmt = lambda v, spec: "—" if v is None else format(v, spec)
    return (f"| {label} | {score} | {sum(r['pass'] for r in declines)}/{len(declines)} | "
            f"{fmt(tokens, ',.0f')} | {fmt(seconds, '.0f')} | {fmt(tool_calls, '.1f')} | "
            f"{gate} | {asked_back} | `{switches}` |")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Hard set: {len(HARD)} questions ({', '.join(HARD)})\n")
    print("| configuration | correct | must-decline refused | tokens / question | seconds / question "
          "| tool calls / question | gate fired | asked back | switches |")
    print("|---|---|---|---|---|---|---|---|---|")
    for label, filename, switches in CONFIGS:
        print(row(label, filename, switches))


if __name__ == "__main__":
    main()
