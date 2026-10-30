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

## Step 1. Topic intent

- `router.intent(question)` returns one of `fees, hostel, calendar, scholarship, placement, admission, people, department, rules, other`, checked in a fixed priority order (hostel → fees → scholarship → placement → calendar → admission → people → department → rules). `respond.answer` adds `intent` to every reply (None for direct replies) and the trace line "Topic: …".
- All 39 `check_answers.py` questions were tagged and read by hand; none needed a special case.
- Also fixed: `check_answers.py --only` overwrote the full results file with just its subset. It now merges.

Done when:

| Check | Result |
|---|---|
| `python test_agentic.py` | **32/32** (29 + 3 new: intents of 20 check questions, priority order, intent in the trace) |
| `python chunk_ranks.py` | 29/32 (unchanged) |
| `python fact_ranks.py` | 15/18 (unchanged) |
| `python evaluate.py` | 16/19 (unchanged) |
| EXPERIMENTS-LOG §21 | written |

## Step 2. Corrective retrieval gate (CRAG)

- `query._rerank` now returns the cross-encoder scores with the order; each result has `"rerank"`. Order unchanged: top-7 ids of 3 questions snapshotted before the change and compared after (identical; pinned in a test).
- New `pipeline/grader.py` (`grade` → correct / ambiguous / incorrect, with `top`, `coverage`, `why`) and `pipeline/grade_calibration.py`.
- `respond.py`: when the grade is not `correct` and `CRAG_GATE` is not `off`, `corrective_passages` looks inside the 2 best-titled pages the first search missed and keeps each one's best passage if its rerank score is above 0. `planner.run(extra=..., search_grade=...)` shows them after the first search's passages and tells the model `Search quality: …`. Trace: "The first search looked weak (…), so I also looked inside “…”." No LLM call added. The one-shot fallback is unchanged.

Commands and results:

```
python grade_calibration.py
  Thresholds: HIGH=3.0, LOW=0.0, COVER=0.75
  Misses graded not correct: 3/3
  Hits graded correct:       20/29
  Must-decline not correct:  5/5
  (full table in EXPERIMENTS-LOG §22)

Budget: placements first agent prompt ≈ 4,613 tokens (+1,200 reply allowance); PROMPT_BUDGET 6,000.

python check_answers.py --only placements --pause 30
  [PASS] placements  (tools: 0, check: verified)      3,688 tokens
  Trace: "The first search looked weak (best match scored -1.2, below 0), so I also looked
          inside “VNIT Nagpur – Training & Placement Department”."
  Answer: "More than 678 students were placed in 2025-26, and over 170 companies participated." [1]
python check_answers.py --only director --pause 30
  [PASS] director  (tools: 0, check: verified)
  [PASS] unanswerable_director_salary  (tools: 2, check: refused)
python check_answers.py --only hostel_fee --pause 30
  [PASS] hostel_fee_first_year, [PASS] hostel_fee_girls, [PASS] unanswerable_old_hostel_fee
```

Done when:

| Check | Result |
|---|---|
| `python test_agentic.py` | **35/35** (3 new: ranking unchanged, grade separates weak/good/other-year, gate puts 678 in the first prompt) |
| `python chunk_ranks.py` | 29/32 (unchanged; it uses `agent.answer`, so it does not see corrective passages) |
| `python fact_ranks.py` | 15/18 (unchanged) |
| `python evaluate.py` | 16/19 (unchanged) |
| `--only placements` | **PASS** (failed in the 30 Oct full run) |
| `--only director`, `--only hostel_fee` | PASS |
| EXPERIMENTS-LOG §22 | written, with the calibration table |

Saved `answer_check.json` now reads 36/39 (the `--only` runs replace just their own questions).

## Step 3. Clarify or assume: slots and a student profile

- New `pipeline/slots.py` (`extract`, `REQUIRED`, `needs_clarification`, `apply_profile`, `clean_profile`).
- `respond.answer(..., profile=None)`: route → topic → apply profile → first search → clarify check (`CLARIFY=off` disables) → corrective gate → planner. A clarification costs no LLM call. A question re-typed right after a clarification is answered as it stands.
- `api/main.py` accepts `profile` (cleaned, never stored). The chat page keeps it in memory, shows choice buttons, re-asks the original question on a click, and has "Clear my details".
- `check_answers.py`: `CLARIFY_CHECKS` with 4 cases.
- Tightened after measuring: the first version asked back on 2 of the 39 (summer-term fee, bus pass) from passages the reranker scored below 3. Only passages scoring ≥ 3.0 now count. Final count on the 39: **0**.

```
python test_agentic.py                                   -> 41/41 passed
respond.answer over all 39 (no key)                      -> clarify on the 39: 0
python check_answers.py --only clarify --pause 30
  [PASS] clarify_hostel_vague  (mode: clarify, choices: ['btech', 'barch', 'msc', 'phd'])
  [PASS] clarify_then_answer  (tools: 0, check: verified)
  [PASS] no_clarify_when_specific  (tools: 0, check: verified)
  [PASS] no_clarify_director  (tools: 0, check: verified)
python check_answers.py --only conv_hostel_girls          -> [PASS]
```

Live API run of the demo (port 8011): "What is the hostel fee?" → clarify (B.Tech, B.Arch, M.Sc, Ph.D) → profile B.Tech → clarify (Boys, Girls) → profile B.Tech girls → "**Rs 32,650** is the total hostel fee for B.Tech girls (double-seater) admitted in 2026-27 [1]", 3 figures verified. A profile of `{"programme": "x; ignore previous"}` is dropped by the API.

Done when:

| Check | Result |
|---|---|
| No-key checks | unchanged (no retrieval change): 29/32, 15/18, 16/19 |
| 4 new cases (`--only clarify` covers `no_clarify` too) | 4/4 PASS |
| `--only conv_hostel_girls` | PASS |
| Tried in the chat page | **Shivanand to try** (steps below); the same requests were tested against the live API |

**Shivanand, try it yourself:**
1. Double-click `start_chatbot.bat` and wait for the chat page to open.
2. Type **What is the hostel fee?** and press Enter.
3. The chatbot asks "Which programme are you asking about?". Click **B.Tech**.
4. It asks "Is this for boys or girls?". Click **Girls**.
5. You should see **Rs 32,650**, with a ✓ badge. Open "How I found this" to see "Assuming B.Tech girls, from earlier in this chat."
6. Click **Clear my details** (under the question box) to make it forget your choices.
