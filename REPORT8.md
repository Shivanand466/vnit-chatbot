# Report 8: agentic upgrades (Runbook 7)

What was done for each step of `RUNBOOK-7-AGENTIC-UPGRADES.md`, the commands run, and the results.

## Step 0. Baseline

- Committed the agentic layer (`1a47128 Agentic layer: router, planner with tools, verifier`). `index.pkl`, `chunks.jsonl` and `data/feedback/` were not staged.
- Tagged `before-runbook-7`. `git checkout before-runbook-7` returns to this point.
- Index backed up to `~/vnit-chatbot-backups/2026-10-30-before-runbook-7/` (`index.pkl` 34.5 MB, `chunks.jsonl` 9.3 MB).

| Check | Command (from `pipeline/`) | Baseline |
|---|---|---|
| Agent unit tests | `python test_agentic.py` | 29/29 passed |
| Answer passage reaches the LLM | `python chunk_ranks.py` | 29/32 within top 7 (26/32 top 3, 30/32 top 12) |
| Answer passage in top 3 | `python fact_ranks.py` | 15/18 |
| Right page in top 3 | `python evaluate.py` | 16/19 = 84% |
| End to end | `python check_answers.py` | 35/39 (saved run, 30 Oct) |

The one-shot baseline (`--pipeline oneshot`) stood at 24/26 with 13 questions not yet asked; it resumes in the background as the gpt-oss-20b allowance refills.
