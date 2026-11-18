# Runbook 8 report: the VNIT website with the chatbot built in

## Step 0. Preflight

- `python --version`: Python 3.13.5 (`~/anaconda3/python.exe`)
- `git --version`: git version 2.52.0.windows.1
- Headless Edge: found at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- `claude` command: not installed, so `run_overnight.sh` cannot run; the steps were done in one interactive session instead.

vnit-chatbot, `git status --short`:
```
 M data/processed/answer_check.json
```
vnit-chatbot, `git log --oneline -3`:
```
c9a3631 100-case check, first day: 13/13 new cases correct, 48/50 overall so far
392e7e0 Answer check grows to 100 cases, written the way students ask
b7d3375 Count quota fallbacks as unanswered in the ablations; README brought up to date
```
Last 3 lines of `data/processed/ablation_runs.log`:
```
  + clarify: [PASS] unanswerable_wifi  (tools: 2, check: verified)
  + clarify: [PASS] hostel_fee_girls  (tools: 0, check: verified)
  + clarify: [PASS] summer_term_fee  (tools: 1, check: unsupported)
```
`run_ablations.sh` process: not running (nor the 100-case runner, halted on 14 Nov).

**Done when:** repo exists with one commit: yes. PROGRESS-8 records Python, Git, Edge and the ablation state: yes.
