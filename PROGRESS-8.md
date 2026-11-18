# Runbook 8 progress

Step 0: DONE - repo created; Python 3.13.5, Git 2.52, Edge found; ablation runner not running

## Decisions

- The `claude` command is not installed on the laptop, so `run_overnight.sh` cannot run. The steps are done one after another in a single Claude Code session from the VS Code extension instead. Same runbook, same rules.

## Next step should know

- Python: `~/anaconda3/python.exe` (3.13.5).
- Edge for screenshots: `/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`.
- Git identity in this repo is copied from vnit-chatbot (Doddi Shivanand).
- vnit-chatbot `git status --short` at Step 0: only ` M data/processed/answer_check.json`. Step 6 must leave it exactly like that.
- No ablation or 100-case runner is running (the 100-case run was halted on 14 Nov at 50 of 100 answered).
