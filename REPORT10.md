# Runbook 10 report: new documents, table rows, freeze and measure

## Good morning

**In short: every test question now passes in the saved results, 105 of 105 (it was 97 of 100).** The last three failures are fixed, five new questions from newly read documents pass, and nothing that passed before broke. The search index is frozen, and the measurements for the report (the ablations) are running in their own window. Everything is committed; nothing is pushed.

**Before and after**

| Check | Before tonight | After |
|---|---|---|
| Answer check, saved results | 97/100 | **105/105** |
| Answer passage reaches the AI's first search (`chunk_ranks`, no key) | 73/77 | **78/82** (the old 77 unchanged, all 5 new ones found 1st) |
| Answer is in what the agent starts from (`evidence_check`, new, no key) | 73/77 + 10/11 | **80/82 + 11/11** |
| Answer passage in the top 3 (`fact_ranks`) | 14/18 | 13/18 (one moved from 2nd to 4th, see below) |
| Right page in the top 3 (`evaluate`) | 16/19 | 16/19 |
| Automated tests (`test_agentic`, no key) | 66/66 | **73/73** |

Of the 105 saved answers, 16 were asked tonight on the final index (all pass). The other 89 are from 14–20 Nov. The fresh full run that the ablations end with will give the headline number on tonight's code.

**New documents.** The website project's full crawl links 116 fee, calendar, hostel, scholarship, placement and rules documents the chatbot had never read.
- All 116 were added to the document list, and every existing entry stayed exactly as it was.
- 53 were processed in the 4-hour limit, newest first: 47 converted, 1 thrown out as a list of people's names, 1 empty, 4 failed.
- **42 are kept** in the search. 4 more are held aside because they pushed right answers out, and 1 Hindi copy (unreadable after scanning) was set aside.
- 62 are still to do; the same command carries on with them.

**The 5 most useful new documents**, each with a new test question that passes:
1. Fees Payment Instruction Summer 2027 (dollar rate for DASA students: ₹96.21)
2. Extension of last date for Fee Remission 2026-27 (14/10/2026)
3. Placement Policy for batch 2027 (offers can be upgraded until 30 April 2027)
4. M.Tech (Research) brochure, January 2027 (5 extra seats per programme)
5. Shiksha Shakti Scholarship 2026-27 (deadline 31 October 2026)

The S-27 fee notice for January–June 2027 is in the search too.

**The 3 table-row misses: all fixed.** Each answer was one row of a long table that the search never brought to the AI. The chatbot now also looks up the two best-matching table rows in code (no extra AI call) for every fee, calendar or placement question, and adds them to what the AI reads.
- **Holi** is now answered 04.03.2026.
- **Companies at B.Tech placements 2024-25** is now answered 121. That row wasn't even in the table store: the reader skipped tables with no paragraph before them, and now it doesn't.
- **Ph.D. part-time tuition** is now answered ₹15,000 per semester.

**Two safety catches found tonight.**
- A converted "refund" notice turned out to be a list of job candidates' names. It had no roll numbers, so the old filter missed it. It is excluded, and a new rule now catches such lists.
- The Hindi placement policy came out of scanning as junk Latin letters. It is excluded, and documents titled as the Hindi version are now skipped.

**Tests that may be out of date:** none found.

**What got worse:** only `fact_ranks`, by one place. The Kotak Kanya question's passage is now 4th, behind the new 2026-27 notice of the same scholarship; both say ₹1.5 lakh a year, and it still reaches the AI.

**The ablations are running** (started 20 Nov 18:28, in the window called "VNIT ablations"). The log already shows answers, for example `one-shot: [PASS] civil_intake`.
- They should finish in **about 3-4 days**. Today's free allowance was mostly used already, so they will mostly wait until tomorrow and then carry on by themselves.
- To check, in Git Bash:
  ```
  cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-chatbot
  tail data/processed/ablation_runs.log
  ```
- When the last line says "all tracks done", run `cd pipeline && python ablation_table.py`.
- **While they run, the free allowance is mostly theirs.** A demo then may be slow or get the simpler answers. To pause them, close their window. To resume, run `cd pipeline && bash run_ablations.sh`; it never asks a question twice.
- Don't change the index or the documents until they finish.

**What to do next**
1. Let the ablations finish, then put the table from `python ablation_table.py` into slides 13-19 (and EXPERIMENTS-LOG §26, README, APPLICATION).
2. Optional, only after that: convert the other 62 documents (`HOW-TO-RUN.md` §5, `convert --only-new`).
3. When you are happy, push:
   ```
   cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-chatbot && git push && git push --tags
   ```
   It triggers the Hugging Face workflow, which skips itself because no `HF_TOKEN` is set.

**Quota used tonight:** about 69,000 tokens of gpt-oss-120b (16 questions). Nothing else used the Groq key, apart from the ablation runner, which started after.


---

## Step 0. Baseline, tag and backups

- `git status` after `24792b0`: clean apart from the untracked `.claude/` and this runbook file (`RUNBOOK-10-DOCUMENTS-TABLE-ROWS-ABLATIONS.md`, committed with Step 0).
- Tag `before-runbook-10` created.
- Backups in `~/vnit-chatbot-backups/2026-11-20-before-runbook-10/`, sizes equal to the originals: `index.pkl` 30,444,574 B, `chunks.jsonl` 8,127,577 B, `facts.db` 8,753,152 B, `inventory.json` 297,623 B, `status.json` 107,866 B.
- `PY` (`~/anaconda3/python.exe`) and `PDFPY` (`~/.venvs/vnit-pdf/Scripts/python.exe`) exist; `import docling` works in `PDFPY`. `~/vnit-secrets.txt` exists and is non-empty (checked with `test -s`, not read).
- Baseline, no key (per-question lists in `../_trash/r10_baseline_*.txt`):

| Check | After Runbook 9 | Step 0 |
|---|---|---|
| Agent unit tests (`test_agentic.py`) | 66/66 | **68/68** (the 66 of Runbook 9 plus the 2 of Step 1, which were already written when this run started; all 66 old ones pass) |
| Answer passage reaches the LLM (`chunk_ranks.py`, top 7) | 73/77 | **73/77** (66/77 in the top 3, 74/77 in the top 12) |
| Answer passage in top 3 (`fact_ranks.py`) | 14/18 | **14/18** |
| Right page in top 3 (`evaluate.py`) | 16/19 | **16/19** |
| End to end (`answer_check.json`) | 97/100 | 97/100 (saved results, not re-asked) |

Not reaching the LLM at baseline: `placements` and `higher_sem_classes_start` (not in the top 12; both pass end to end, through the corrective step and the agent's tools), `holiday_holi` (rank 9), `companies_btech_2425` (not in the top 12).

**Done when:** tag and backups exist; Pythons, Docling and the key file are checked; the baseline table is here. **Met.**

## Step 1. The 116 documents added to the inventory, from the saved crawl

- New in `ingest_documents.py`:
  - `links_on` finds a page's document links; `discover()` now calls it, with the same rules as before.
  - `add_metadata` is shared by `discover()` and the new action.
  - `crawl_links` reads the saved crawl (read-only, nothing fetched).
  - `crawl_candidates` holds the selection that `count_new_documents.py` used to do itself; it now calls this.
  - `merge_inventory` only adds keys and writes through a temporary file that is then renamed.
  - New action `discover-crawl`, and a `--only-new` flag for `convert` and `plan` that limits them to the keys listed in `data/documents/added_*.json`.
- Run: `PDFPY ingest_documents.py discover-crawl`.
  - 5,098 document links in the crawl.
  - **116 added**, with 0 metadata errors.
  - Skipped: 529 already in the inventory; 4,375 not about fees, calendar, hostel, scholarship, placement or rules; 45 lists of people or procurement; 22 with the title of a document already known; 11 with the same title as another new link.
  - The count reproduces Runbook 9's 116. The one difference is 45 lists of people instead of 44, because link texts are now kept to 200 characters, as `discover()` keeps them, instead of 150.
- Check against the backup (script): the inventory had 599 entries and now has 715. **Every existing entry is unchanged** (keys and values compared). The new keys are exactly the 116 in `data/documents/added_2026-11-20.json`.
- `plan --only-new`: **115 of the 116 are in tier 0** and none in tiers 1 or 2.
  - The Summer 2027 fee instructions are in tier 0.
  - The one not selected is "Engineers India Limited (EIL) Scholarship to SC & ST students 2022 Batch only (Application…)": its title matches the blank-forms rule. The tiers were not changed.
  - No old document is left unprocessed, so `convert` would only pick up new ones; `--only-new` is used anyway, as a safeguard.
  - The newest 10 in conversion order:
    - Extension Notice for NSP Scholarship (2026-11-16)
    - S-27-Fee Notice Even Term – Academic Year 2026-27 – UG-PG
    - Fees Payment Instruction Summer 2027
    - SOP for Semester Fee Payment Summer 2027
    - Student Feedback Notice
    - Student Feedback SOP
    - Notice for Mandatory Submission of Online Course Feedback for W26
    - Notice for Extension of the Last Date for filling the Course Feedback
    - Notice – Refund of Caution Deposit…
    - National Overseas Scholarship (NOS) Scheme for ST students

  The full list is in `../_trash/r10_plan.txt`.
- New tests, no key and no internet:
  - `test_crawl_documents_skip_known_links_people_lists_and_other_topics` (a fake crawl: a known link isn't added again, a link seen twice is added once, a merit list and an off-topic title are skipped);
  - `test_inventory_merge_keeps_every_existing_entry` (a temporary inventory: existing entries unchanged even when offered a new value, re-adding adds 0, no temporary file left).

  Both pass.

**Done when:** existing entries unchanged plus about 116 new ones; plan output here. **Met.**

## Step 2. Conversion

- Run: `PDFPY ingest_documents.py convert --tiers 0,1,2 --only-new`, in the background, log in `../_trash/convert.log`.
  - Started about 10:33. Stopped at the **4-hour timebox (14:35)**.
  - Documents took 35 s to 11 min each. They were slowest while the evidence baseline (Step 4's script) ran beside them.
  - The worker was stopped cleanly. Finished documents are kept in `status.json`. The document in progress at the stop was not recorded, so it is retried next time; its stale `in_progress.txt` was moved to `_trash/`.
- **Counts, of the 115 selected:**
  - 53 processed: **47 converted and kept**, 1 converted then excluded as personal data, 1 empty, 4 failed. That is the 48 converted by the converter, minus the 1 excluded after it.
  - **62 still to do.** `convert --only-new` carries on with them when run again.
- **Failed (4):** Ph.D. admission brochure January 2027 (timeout), SOP for Semester Fee Payment Summer 2025 (timeout), SOP Winter 2025 (timeout), ONGC Scholarship 2024-25 (worker crashed). Retry those with `VNIT_DOC_TIMEOUT` set higher.
- **Empty (1):** "Detailed Brochure" (8 words, an image PDF).
- **10 converted titles, the most useful first:**
  1. S-27-Fee Notice Even Term – Academic Year 2026-27 – UG-PG (1,025 words)
  2. Fees Payment Instruction Summer 2027 (751)
  3. SOP for Semester Fee Payment Summer 2027 (1,621)
  4. Information Brochure, Rules and Regulations for admission to M.Tech (Research) Program January 2027 (4,162)
  5. Placement Policy_Batch 2027 (2,259)
  6. Kotak Kanya Scholarship 2026-27 (97)
  7. Shiksha Shakti Scholarship 2026–27 (308)
  8. Extension of last date for Fee Remission 2026-27 application (84)
  9. National Overseas Scholarship (NOS) Scheme for ST students (4,023)
  10. Information Brochure for International Admissions – 2026 (591)
- **Privacy re-check** over every new `doc_*.txt`: `looks_like_personal_data` false and no `STUDENT_ROLL` match. This passed for all 48, but reading the largest one found it is a list of people.
  - "Notice – Refund of Caution Deposit and Partial Application Fee in respect of candidates applied for non-academic posts…" (12,861 words) is mostly an annex of recruitment candidates' names. It has no roll numbers, so no rule caught it.
  - Fixed generally: a new rule, `PERSON_LABEL`, flags text with at least 10 "Name of the candidate/student/applicant" labels and at least 1 per 100 words.
  - Measured over all 454 documents then in `data/raw`, it flags only this one. The densest of the older documents, a department brochure with its students' placements, has 0.85 per 100 words and is unchanged, because existing entries stay as they are.
  - The file was moved to `_trash/r10-personal-data/` and its new `status.json` entry is marked `personal_data`, with the reason.
  - New test: `test_a_list_of_candidates_names_is_personal_data`.
- `status.json`: 456 entries before and 509 now. **Every existing entry is unchanged**, and every new key comes from `added_2026-11-20.json` (checked by a script against the backup).

**Done when:** conversion timeboxed; counts and 10 titles here; privacy re-check passes (after the one exclusion). **Met.**

## Step 3. Rebuild and measure: keep only what helps

Full numbers and reasons: EXPERIMENTS-LOG §34. Per-question lists: `../_trash/r10_s3*_*.txt`.

- **First rebuild, all 47 new documents** (7,369 chunks): `chunk_ranks` **lost 2 baseline hits**: `barch_tuition` went from 5 to 9 and `msc_tuition` from 7 to 10.
  - Their places went to 4 new documents that are not newer versions of those fee sheets: International Admissions brochure 2026, MahaDBT freeship, S25 fee notice 2024-25, and Revised W25 fee notice 2025-26.
  - These were moved to `data/raw_new_docs_held/`.
- **Second rebuild** (7,339 chunks): `chunk_ranks` kept everything, but `evidence_check` (Step 4's script, no key) showed `placements` lost.
  - It had reached the agent only through the corrective step. The new *Placement Policy_Batch 2027 (Hindi)* now took one of the corrective step's two places.
  - Its text is OCR noise. Fixed in general: `select()` skips titles naming the Hindi version. The file was moved to `_trash/r10-hindi/` and marked `hindi` in `status.json`. Test: `test_a_hindi_version_is_not_selected`.
- **Kept index** (third rebuild): **7,328 chunks** from 529 files: 81 web pages and 448 documents, 42 of them new tonight. `facts.db` holds 23,457 table records (was 23,088).

| Check | Step 0 | Kept index |
|---|---|---|
| `test_agentic.py` | 68/68 | **70/70** |
| `chunk_ranks.py` (top 7) | 73/77 | **78/82**: the old 73/77 unchanged, plus all 5 new cases at rank 1 |
| `fact_ranks.py` | 14/18 | **13/18**: the Kotak Kanya question moved from 2nd to 4th, behind the new 2026-27 notice of the same scholarship (both give ₹1.5 lakh); it still reaches the AI. This is the one allowed trade. |
| `evaluate.py` | 16/19 | **16/19** |
| `evidence_check.py` (fact questions) | 73/77 | **78/82**, with every baseline hit kept; conversation and profile cases 10/11, also unchanged |

- **Tests that may be out of date:** none.
- **The 5 new cases** written from the documents' own text, now in `check_answers.py`; the set is 105 cases:
  - `dasa_usd_rate_summer_2027` (₹96.21)
  - `fee_remission_2627_extended` (14/10/2026)
  - `shiksha_shakti_deadline` (31 Oct 2026)
  - `placement_offer_upgrade_2027` (30 April 2027)
  - `mtech_research_seats_2027` (5 per programme)

  All 5 rank 1. A sixth, the S-27 fee-payment last date, wasn't in the top 12, so it was replaced rather than loosened.

**Done when:** decision and numbers in §34, kept index on disk, 5 new cases written. **Met.**

## Step 4. The 3 table-row misses

Details of every attempt: EXPERIMENTS-LOG §35.

- **Kept:** option 1, table rows as corrective passages (`respond.table_rows`, code only, no LLM call). For fees, calendar and placement questions, the best 2 rows of `facts.db` are added to the agent's first evidence. The trace adds "I also looked up matching rows in the documents' tables." Four general fixes were needed:
  - rows are ranked by the rare question words in their own label and cells;
  - no "already shown" filter;
  - one row per document;
  - "B.Tech" is matched as "btech".

  The table parser also learnt the row shape used by tables with no paragraph before them, so `facts.db` grew from 23,457 to **31,682** records. That is how the "Number of Companies Visited — B.Tech: 121" row got in.
- Each added row is capped at 450 characters. The largest first prompt measured is 5,374 tokens, under the 6,000 budget.
- Option 2 (look inside the best document) was measured first and not built: inside the placement report, the statistics passage still isn't in the top 8 of 30. Option 3 wasn't needed.
- `CRAG_GATE=off` switches the rows off too, so the ablations stay consistent.

| The 3 misses | Before | Now |
|---|---|---|
| `holiday_holi` | not in the evidence (rank 9) | **in the evidence** (row "Holi — Date: 04.03.2026; Day: Wednesday") |
| `companies_btech_2425` | not in the evidence | **in the evidence** (row "Number of Companies Visited — B.Tech: 121") |
| `conv_phd_part_time` | not in the evidence (rank 10) | **in the evidence** (row "Tuition Fees — Ph.D. (Part-Time) Per Sem.: 15000.00") |

| Check | After Step 3 | After Step 4 |
|---|---|---|
| `evidence_check.py` (new, no key), fact questions | 78/82 | **80/82** |
| `evidence_check.py`, conversations and profile cases | 10/11 | **11/11** |
| `chunk_ranks.py` | 78/82 | **78/82** (every rank identical; the first search did not change) |
| `test_agentic.py` | 70/70 | **73/73** |

- `fact_ranks` and `evaluate` call the search directly, which didn't change, so they stay at 13/18 and 16/19.
- New tests:
  - `test_table_parser_takes_a_row_without_a_lead_in`
  - `test_table_rows_bring_the_one_row_of_a_long_table` (all three rows, real `facts.db`, skipped when it's missing)
  - `test_table_rows_only_for_fees_calendar_and_placement`

**Done when:** each of the 3 is in the evidence; `chunk_ranks` and `evidence_check` no lower than after Step 3; tests pass. **Met.**

## Step 5. Asking the AI: the 3 misses, the new-document questions, regression

There are 16 cases, asked one at a time through the agent. That is 15 answers plus 1 clarifying question that needs no LLM, about **69,000 tokens** in all. The full table is in EXPERIMENTS-LOG §36.

- **The 3 table-row misses: all PASS.** Holi gives 04.03.2026, the companies question 121, and the Ph.D. part-time question ₹15,000 per semester.
- **The 5 new-document questions: all PASS:**
  - DASA USD rate: ₹96.21
  - fee remission 2026-27 extended to 14/10/2026
  - Shiksha Shakti deadline: 31 Oct 2026
  - placement offer upgrade until 30 April 2027
  - M.Tech (Research): 5 seats per programme
- **Regression, 8 cases: all PASS:** placements, btech_fee_open, hostel_fee_girls, msc_tuition, phd_tuition_full_time, midsem_slot_a, unanswerable_wifi, clarify_tuition_vague.
- Every answer's figures were verified against the passages. Nothing needed reverting.
- **Total from the saved results: 105/105**, up from 97/100. The other 89 are saved answers from 14–20 Nov; Step 6's fresh full run measures all 105 on tonight's code.
- No daily-limit message appeared; nothing is waiting.

**Done when:** all asked; before/after table in EXPERIMENTS-LOG §36. **Met.**

## Step 6. Freeze the index and start the ablations

Steps 3–5 ended with a kept, working index and no regression, so this step ran.

- **Frozen.**
  - Tag `final-index-2026-11-20` (at commit `3cfea23`).
  - Copy in `~/vnit-chatbot-backups/final-index-2026-11-20/`, sizes equal to the originals: `index.pkl` 32,383,236 B, `chunks.jsonl` 8,626,639 B, `facts.db` 10,977,280 B.
  - EXPERIMENTS-LOG §26 now says every ablation row from here on uses this index, and why the older rows are set aside.
- **Old results set aside** in `data/processed/results-before-2026-11-20/`:
  - moved: `answer_check_oneshot.json`, `_no_tools`, `_agent_30oct`, `_crag`, and the old `ablation_runs.log`, as `ablation_runs_before_2026-11-20.log`;
  - copied: `answer_check.json` (the 105/105 record, tonight's Step 5 answers included).
- **What was checked in `run_ablations.sh` and `check_answers.py`:**
  - Every agent configuration writes `answer_check_<config>.json` (`results_path`). The final full run uses `--config full`, so it writes `answer_check_full.json` and never reads `answer_check.json`. The headline number will be a fresh run of all 105 on the frozen index, with no change needed.
  - The one-shot track writes `answer_check_oneshot.json`. That file was moved aside, so it starts afresh too.
- **Started** in its own window ("VNIT ablations") with `cmd //c start "VNIT ablations" "C:\Program Files\Git\bin\bash.exe" -lc "cd …/pipeline && bash run_ablations.sh"`. Git Bash is at `C:\Program Files\Git\bin\bash.exe`. The log shows:
  ```
  [20 Nov 18:28] started
  [20 Nov 18:28] one-shot: attempt 1
  [20 Nov 18:28] agent, no tools: attempt 1
  ```
- From here, the index, `data/raw` and the retrieval code stay as they are. Step 7 only edits docs.

**Done when:** tag and frozen copy exist; old results set aside; runner confirmed started. **Met.**

## Step 7. Docs and the morning report

- `README.md`:
  - project status: documents 448, the index frozen with 7,328 chunks and 31,682 table cells, 105/105, 105 cases, tests 73/73, ablations running;
  - measured quality: `chunk_ranks` 78/82, the new `evidence_check` 80/82 + 11/11, `fact_ranks` 13/18;
  - known limitations: table rows found by a separate lookup, 62 documents still to convert, the privacy filter's new rule;
  - what to do next.
- `APPLICATION.md`: status table (same numbers), and the corrective step's new table rows described in §5a B.
- `HOW-TO-RUN.md`:
  - how to run `discover-crawl`, `plan --only-new` and `convert --only-new`, in the same plain style, with a warning not to do it while the ablations run;
  - `evidence_check.py` in the checks; the test count 73/73;
  - `data/raw_new_docs_held/` in the folder table.
- **Website check** (no key, port 8010, `uvicorn api.main:app --port 8010`, stopped afterwards; port 8010 confirmed free):
  - `/health` ok;
  - `/site/` 200 ("Home | VNIT Nagpur (student project demo)");
  - `/ask` "is holi a holiday at vnit in 2026? which date?" gave `extractive (no GENAI_API_KEY set)` passages from "List of Holiday's during the year 2026";
  - `/ask` "What is the hostel fee?" gave `clarify` (btech, barch, mtech, phd).

  The website in `../vnit-website` was not rebuilt or changed.

**Done when:** docs updated, every step marked, last commit in. **Met.**
