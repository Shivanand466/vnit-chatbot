# Runbook 11 report: agent v2

## Good morning

(Written at the end, in Step 10.)

## Step 0. Worktree, branch, frozen index, dev model, baseline

- **The ablations are running and were not touched.** Log tail at the start (00:50, 21 Nov): `one-shot: Answer check (oneshot): 74/85 passed (20 not asked yet)`, stopped for the day's allowance as expected; the runner retries every half hour. No Python process of theirs was running at that moment (they were waiting).
- **Worktree:** `git -C vnit-chatbot worktree add ../vnit-chatbot-v2 -b agent-v2 final-index-2026-11-20`, then `merge --ff-only ddcb7cd` fast-forwarded (docs only). `vnit-chatbot/`'s `git status --short` before and after: identical (only the ablations' three untracked result files and `.claude/`), still on `main` at `ddcb7cd`.
- **Frozen index** copied from `~/vnit-chatbot-backups/final-index-2026-11-20/`: `index.pkl` 32,383,236 bytes, `chunks.jsonl` 8,626,639, `facts.db` 10,977,280, the same sizes as v1's (and `index.pkl`'s MD5 is identical). Not in git.
- `data/feedback/` created empty; no students' data copied.
- **Dev model:** `GET /models` lists `allam-2-7b`, `canopylabs/orpheus-*` (speech), `meta-llama/llama-prompt-guard-2-*`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b`, `whisper-*`. None of the preferred ones (kimi-k2, qwen3-32b, llama-3.3-70b, llama-4) exists for this key, so **`DEV_MODEL = qwen/qwen3.8-27b`**: a general model with its own allowance. A tiny tool-calling test returned a correct `tool_calls` reply (305 tokens; limits 8,000 tokens a minute).
- **Baseline in the worktree, no key** (logs in `../_trash/r11/`):

| Check | REPORT10 | Worktree |
|---|---|---|
| `test_agentic.py` | 73/73 | **73/73** |
| `chunk_ranks.py` (top 7) | 78/82 | **78/82** |
| `fact_ranks.py` | 13/18 | **13/18** |
| `evaluate.py` | 16/19 | **16/19** |
| `evidence_check.py` | 80/82 + 11/11 | **80/82 + 11/11** |

**Done when:** worktree on `agent-v2` with the frozen index, `vnit-chatbot/` unchanged, dev model recorded, baseline equals REPORT10. **Met.**

