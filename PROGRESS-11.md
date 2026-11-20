# Runbook 11 progress

Read this first after a restart; carry on from the first step not marked DONE, PARTIAL, FAILED or SKIPPED.
Work happens only in this worktree (`vnit-chatbot-v2/`, branch `agent-v2`) and, in Step 8, on `vnit-website`'s branch `agent-v2`.

`DEV_MODEL = qwen/qwen3.8-27b` (Groq; tool calling works; its own allowance, not the ablations' gpt-oss models)

| Step | Status | Note |
|---|---|---|
| 0 | DONE | worktree on agent-v2 from the frozen tag + ff to ddcb7cd; index copied; DEV_MODEL qwen/qwen3.8-27b; baseline 73/73, 78/82, 13/18, 16/19, 80/82 + 11/11 |
| 1 | DONE | memory.py: 6 turns, 600 chars, ~1,500 tokens; turns in /ask; rewrite sees answers; earlier answers never evidence; AGENT_V2=off = v1 |
| 2 | DONE | agent_loop.py: plan, 6 rounds, 3 parallel calls, budget 14k, stuck/plan-done stops, code reflection, compaction, repeat-call skip; live 3 multi-part: 2 right, 1 half (placements 2025-26) |
| 3 | DONE | latest_notices, fetch_vnit_page (vnit.ac.in only, cache, crawl fallback), today, contact_office; live: latest_notices used; deadline question didn't call today (recorded) |
| 4 | DONE | router.task: 7 task types, task lines, labelled general answers, draft label; live one of each type right (summary went over budget, recorded) |
| 5 | DONE | language.py: hi/mr/hinglish detection, English first search, answer in kind, Devanagari digits; live Hindi, Marathi, Hinglish all right |
| 6 | DONE | /ask/stream SSE (step, token, replace, done, error), worker thread, ping, Stop cancels, suggestions; done JSON == /ask in test; curl -N on 8020 |
| 7 | DONE | new chat page: streaming with live steps, Stop, Copy, Regenerate, Edit, suggestions, New chat, empty state, tables, 360 px; old features checklist kept; escaping checked; screenshots in checks/ |
| 8 | DONE | vnit-website branch agent-v2 (0ced9ea): widget streams with live steps, Stop, Copy, Regenerate, suggestions, tables, /ask fallback; site rebuilt, 0/0/0 in the three checks; master unchanged |
| 9 | | |
| 10 | | |

## Decisions

- Step 0: Groq lists no `kimi-k2`, `qwen3-32b`, `llama-3.3-70b` or `llama-4` model for this key; `qwen/qwen3.8-27b` is the only general model besides the two gpt-oss ones (the others are Arabic/English speech, Whisper, prompt guards and a 7B model), and a 20-token tool-call test returned a correct `tool_calls` reply, so it is the dev model.
- Steps 1-6: written together, since they share `respond.py`, `api/main.py` and the test files, and `git add -p` isn't available here. They are committed one step at a time by file (the step that introduced each file), so a single commit in the middle may not run on its own; the commit of Step 6 is the first complete one, and all the checks were run on the full code.
- Step 0/1: `respond.py` was changed only after the baseline's last check (`evidence_check.py`) had imported it, so the baseline measured unchanged code.
- Step 2: the prompt size for `PROMPT_BUDGET` is measured as planner.py measures it (without the reply allowance); compaction never happens before the first round, so the first prompt has the same passages as v1's.
- Step 2: `planner._LLM.chat` got optional `schemas` and `extra` arguments rather than a copied client, as the runbook asks ("don't fork them").
- Step 3: `today` stays a tool, but today's date also stays in the prompt (v1 has it there and the final prompt needs it), so the model rarely calls `today`; recorded rather than removing the date.
- Step 3: `run_tool` runs v2's tools for v2 names only; v1 never offers them, and an unoffered call is refused by Groq (400) before it reaches `run_tool`.
- Step 4: a general answer's figures are flagged with a softer note ("general information, not checked against VNIT's documents") instead of "could not confirm", since "10-point scale" is a figure of a definition, not a VNIT claim.
- Step 4: the agent's suggestions are chosen in code from questions the saved results show are answered right, rather than written by the model, so a suggestion never leads to a dead end and costs nothing.
- Step 5: Hinglish needed "hoga", "shuru" and similar words in the detection list: "exam kab shuru hoga?" has only one of the first list.
- Step 6: `fake_llm.py` (`AGENT_FAKE_LLM=on`) was added so the chat page can be shown and screenshotted on 8020 without spending any Groq allowance; its answers carry the mode "agent v2 (fake-llm)".
- Step 7: screenshots are taken with `tools/cdp_shot.py` (Edge through its DevTools protocol, using the `websocket-client` package that came with Anaconda), because `--screenshot` fires before a streamed answer finishes. It is a development tool only. PNGs are in `checks/` (git-ignored).
- Step 7: the chat page accepts `/?q=<question>` to ask on opening; it is what the screenshots use, and lets the website link straight to an answer.
- Step 8: `vnit-website` itself is on branch `agent-v2` (as the runbook says), so v1's server on 8000 also serves the new widget from `dist/`; the widget falls back to `/ask` when `/ask/stream` is missing, so v1 keeps working with it. `git -C vnit-website switch master` and a rebuild give the old widget back.
- Step 9: the dev model's rolling daily allowance (~200,000 tokens) ran out during the agentic set, after about 160,000 tokens of Steps 2-5 trials; a background loop resumes the agentic set, then the regression spread, every 20 minutes until 07:30.
