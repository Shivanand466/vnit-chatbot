#!/bin/bash
# Runs every measurement of EXPERIMENTS-LOG §26 unattended, over as many days
# as Groq's free daily allowance needs (about three).
#
# Two tracks run side by side, because each model has its own daily allowance:
#   gpt-oss-20b    the one-shot baseline, all questions
#   gpt-oss-120b   the agent: five configurations on the hard set, then one
#                  full run of everything (the headline number)
# When a run stops because the day's allowance is spent (check_answers.py exits
# with 2), it waits 30 minutes and carries on with --resume, which never asks a
# question twice. Safe to stop and start again at any time.
#
# Start it from Git Bash, in the pipeline folder:
#     bash run_ablations.sh
# Progress goes to ../data/processed/ablation_runs.log. When both tracks say
# "done", run:  python ablation_table.py

cd "$(dirname "$0")" || exit 1
PY="${PY:-$HOME/anaconda3/python.exe}"
LOG=../data/processed/ablation_runs.log
export GENAI_API_KEY=$(head -1 ~/groq-key.txt | tr -d '\r\n ')
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

# One job: run it until check_answers.py says it is complete.
job() {
  local name=$1; shift
  for attempt in $(seq 1 200); do
    echo "[$(date '+%d %b %H:%M')] $name: attempt $attempt" >> "$LOG"
    env "$@" --resume 2>&1 | grep --line-buffered -E "^\[(PASS|FAIL)\]|Answer check|STOPPED"       | sed -u "s/^/  $name: /" >> "$LOG"
    if [ "${PIPESTATUS[0]}" -eq 0 ]; then
      echo "[$(date '+%d %b %H:%M')] $name: done" >> "$LOG"
      return 0
    fi
    sleep 1800
  done
  echo "[$(date '+%d %b %H:%M')] $name: gave up after 200 attempts" >> "$LOG"
}

oneshot_track() {
  job one-shot "$PY" check_answers.py --pipeline oneshot
}

agent_track() {
  job "agent, no tools" AGENT_TOOLS=off CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off \
      "$PY" check_answers.py --set hard --config no_tools
  job "agent (30 Oct)" CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off \
      "$PY" check_answers.py --set hard --config agent_30oct
  job "+ CRAG gate" CLARIFY=off LOOKUP_TABLE=off \
      "$PY" check_answers.py --set hard --config crag
  job "+ clarify" LOOKUP_TABLE=off \
      "$PY" check_answers.py --set hard --config clarify
  job "full (hard set)" "$PY" check_answers.py --set hard --config full_hard
  job "full (all questions)" "$PY" check_answers.py --config full
}

# Stopping this script (Ctrl+C, closing the window) stops both tracks too.
trap 'kill 0' INT TERM
echo "[$(date '+%d %b %H:%M')] started" >> "$LOG"
oneshot_track &
agent_track &
wait
echo "[$(date '+%d %b %H:%M')] all tracks done; run: python ablation_table.py" >> "$LOG"
