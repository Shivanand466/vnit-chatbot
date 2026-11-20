# Runbook 11 progress

Read this first after a restart; carry on from the first step not marked DONE, PARTIAL, FAILED or SKIPPED.
Work happens only in this worktree (`vnit-chatbot-v2/`, branch `agent-v2`) and, in Step 8, on `vnit-website`'s branch `agent-v2`.

`DEV_MODEL = qwen/qwen3.8-27b` (Groq; tool calling works; its own allowance, not the ablations' gpt-oss models)

| Step | Status | Note |
|---|---|---|
| 0 | DONE | worktree on agent-v2 from the frozen tag + ff to ddcb7cd; index copied; DEV_MODEL qwen/qwen3.8-27b; baseline 73/73, 78/82, 13/18, 16/19, 80/82 + 11/11 |
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |

## Decisions

- Step 0: Groq lists no `kimi-k2`, `qwen3-32b`, `llama-3.3-70b` or `llama-4` model for this key; `qwen/qwen3.8-27b` is the only general model besides the two gpt-oss ones (the others are Arabic/English speech, Whisper, prompt guards and a 7B model), and a 20-token tool-call test returned a correct `tool_calls` reply, so it is the dev model.
