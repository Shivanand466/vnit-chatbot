# Placements fix and key cleanup

Run on: 2026-09-21 (Windows 11, Git Bash + Anaconda Python 3.13.5, via Claude Code). No project code was modified; all experiments below were run in memory against the unmodified files.

## Read this first: runbooks and reports were moved
At Shivanand's request, all `RUNBOOK-*.md` and `REPORT.md`–`REPORT5.md` files were moved (not deleted) out of `vnit-chatbot/` into:

```
VNIT-Website-Chatbot/_archive-runbooks-and-reports/
├── RUNBOOK-FOR-CLAUDE-CODE.md, RUNBOOK-2 … RUNBOOK-6
├── REPORT.md, REPORT2.md … REPORT5.md
└── claude-outputs-copies/   <- duplicate RUNBOOK-FOR-CLAUDE-CODE.md and RUNBOOK-2 that were in FYP/Claude outputs/
```

`APPLICATION.md`, `README.md` and `EXPERIMENTS-LOG.md` stay in `vnit-chatbot/`. `APPLICATION.md` still links to `RUNBOOK-*`/`REPORT*` by bare filename, so those links now point at the archive folder. This report (`REPORT6.md`) is in `vnit-chatbot/` as the runbook asked. Put future runbooks wherever suits you; I'll look in both places.

## Step 1 — old key revoked?
Confirmed dead: **No.**
```
gsk_GIUR... (old key, rounds 1-4):  GET /openai/v1/models -> HTTP 200
gsk_xorM... (newer key, round 5):  GET /openai/v1/models -> HTTP 200
```
Revoking a key needs a person in the Groq console, so I can't do it from here. Shivanand has not deleted it yet. Both keys are still live and both are in the chat transcript. **Both should be deleted** at console.groq.com → API Keys, and a fresh key created that never gets pasted into chat. Tests this round used the newer key.

## Step 2 — placements question re-test
mode: `llm (openai/gpt-oss-20b)`
sources: `section/academics/notice-new`, `section/academics/notice/`, `academic-programs`, `section/tnp/`, `engineering/mech/`, `centre-for-innovation`
answer: "The provided passages do not contain any information about the number of students placed in 2025-26 or the number of companies that participated."
Fixed?: **No, but the cause is now exact and a fix has been tested.**

Preconditions confirmed: `index.pkl` is the embeddings index (417 chunks), and both `agent.py` (`whole_question_results`) and `generate.py` (the merge loop) have the round-5 fix.

### Why the fix didn't work: the stats chunk loses a budget race by 27 characters
`whole_question_results` does retrieve the stats chunk (#2 of 3, `section/tnp/`, 1,161 chars, "678 students" at char 696, "170 reputed organizations" at char 859). But `generate.py` fills the 6,000-char budget with the six sub-question chunks **first**, and only merges whole-question results into what's left. I replicated the exact `_add_chunk` logic:

```
sub-question chunks (6):          788 + 785 + 758 + 779 + 581 + 769  -> total 4460
whole-question #1 (tnp, no stats):                               783  -> total 5243
whole-question #2 (tnp, HAS 678): 5243 + 784 = 6027 > 6000  -> REJECTED, loop breaks
```
The chunk the fix exists to add is refused by 27 characters, because the six weak sub-question chunks were admitted first. The merge logic is correct, but its priority order leaves it no budget.

There is also a second, smaller cap: `MAX_CHUNK_CHARS = 700` truncates this chunk after char 700. "678" (char 696) just survives it, but "170 reputed organizations" (char 859) does not, so even a fix that lets the chunk in only recovers half the answer at 700.

### Experiments (in memory, real Groq calls, project files unchanged)
| Config | Stats chunk in prompt? | Context size | Answer |
|---|---|---|---|
| **Current code**: sub-questions first, 6000 / 700 | No | 5,541 | "not in passages" |
| Raise total cap only: 8000 / 700 | Yes (truncated) | — | **678 students** ✓, companies "not given" ✗ |
| Raise both caps: 8000 / 1200 | **No** — bigger earlier chunks push it out again | — | "not in passages" (worse) |
| Whole-question first, 6000 / 700 | Yes (truncated) | 5,661 | **678 students** ✓, companies "not given" ✗ |
| **Whole-question first, 6000 / 1000** | **Yes, complete** | **5,489** | ✓ **"More than 678 students … placed in the 2025-26 placement season, with offers from over 170 reputed organisations" [Training & Placement — section/tnp/]** |

**Recommended fix (the last row):** in `generate.py`'s `llm_answer()`, move the `whole_question_results` loop **before** the per-sub-question loop, and raise `MAX_CHUNK_CHARS` from 700 to 1000. This gives the full correct answer with a **smaller** prompt than the current code (5,489 vs 5,541 chars), so the 429 risk doesn't go up. It also matches the idea behind the fix: the whole question keeps the shared context, so its best chunks should get budget first.

Caveats Cowork should check before adopting it:
- Just raising caps is not a fix, as row 3 shows: bigger caps change which chunks win the budget and can make things worse.
- Changing `MAX_CHUNK_CHARS` changes what every question sends, so re-run the Civil and 5G questions (see below) and a few others. I tested only the placements question under the new config.
- `_add_chunk` returning `False` causes a `break`, so one oversized chunk stops a smaller later one that would still fit. Consider `continue` instead.

## Step 3 — benchmark regression check
Hit-rate: **17/19 = 89%**, unchanged from REPORT5.md (embeddings). Same two misses: Electrical M.Tech (top result `engineering/mining`) and Registrar phone (top result `rti-officer`). As the runbook expected, this change doesn't affect retrieval scoring.

## Anything else worth flagging
- **Earlier fixes still hold against the current code:** I re-ran both through the live API this round.
  - Civil: "The Civil Engineering Department at VNIT Nagpur enrolls **120 undergraduate students each year** [Civil Engineering Department — engineering/civil/]"
  - 5G: "...officially announced during a virtual ceremony hosted by Prime Minister Narendra Modi at the Indian Mobile Congress (IMC-23) in New Delhi on **27 October 2023**" [5G Lab VNIT Nagpur]
- **Honesty behavior still solid:** in every config where the stats chunk was missing or truncated, the LLM said the figure wasn't in the passages. It never invented a placement count or a company count, even in the half-answer cases.
- `APPLICATION.md` section 2 / 12 should be updated once Cowork decides on the fix. I left it untouched apart from what's described here, since its "Currently open task" wording depends on Cowork's next move.
- All servers stopped, ports 8000/8001 free, no Python processes left running. Server logs are in Claude Code's scratchpad, not the project.
