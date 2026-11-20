# Runbook 10: new documents, the last 3 table-row misses, then freeze and measure

**For:** Claude Code, running unattended overnight on Shivanand's Windows laptop (VS Code extension, same as Runbooks 8 and 9), in `FYP\VNIT-Website-Chatbot\vnit-chatbot`.
**Why:** after Runbook 9 the chatbot scores **97/100** (commit `4e1da48`). Three things are left before the final numbers can be measured:
1. 116 fee, calendar, hostel, scholarship and placement documents that the full crawl links to have never been read, among them the Summer 2027 fee instructions, the S-27 fee notice for 2026-27, the January 2027 Ph.D. brochure and the 2026-27 scholarships (REPORT9 Step 6).
2. The last 3 failures all come from one row of a long table never reaching the AI: Holi (ranks 9th), the 121 companies (64th before reranking), and Ph.D. part-time tuition ₹15,000 (10th, the AI answered with the ₹25,000 total row) (REPORT9 Steps 3 and 7).
3. The ablation table (EXPERIMENTS-LOG §26) was measured on an older index. It must be re-run on the **final** index, so the index has to be finished and frozen first.

So the order is fixed: documents, then table rows, then freeze, then start the ablations.
**Owner:** Shivanand directs and is a beginner at app building. He is asleep. In the morning he reads the "Good morning" section of `REPORT10.md`.

---

## How this runbook is run

One Claude Code session, started with:

> Read RUNBOOK-10-DOCUMENTS-TABLE-ROWS-ABLATIONS.md and PROGRESS-10.md (if it exists). Do every step from the first one not marked in PROGRESS-10.md through Step 7, in order, without stopping between steps, following "Ground rules". After each step: run its "Done when" checks, write the results into REPORT10.md, mark the step in PROGRESS-10.md, and commit. Never ask a question.

If the session is compacted or restarted, PROGRESS-10.md is the memory.

| Step | What | Rough time | Groq quota |
|---|---|---|---|
| 0 | Baseline, tag and backups | 20 min | none |
| 1 | Add the 116 documents to the inventory, from the saved crawl | 45 min | none |
| 2 | Convert them | 2–4 h, unattended | none |
| 3 | Rebuild and measure: keep only what helps | 1.5 h | none |
| 4 | The 3 table-row misses | 2 h | none |
| 5 | Ask the AI: the 3, new-document questions, regression | 1 h | ~90k tokens |
| 6 | Freeze the index and start the ablations | 30 min | the runner's own |
| 7 | Docs and the morning report | 30 min | none |

---

## Ground rules (every step)

Runbook 9's ground rules all apply: never ask, decide and record under "Decisions"; failed steps revert, get marked `FAILED` and the run moves on; `PY=~/anaconda3/python.exe`; general fixes only, never code naming a test question, page or fact; no new LLM calls in the live path; no new dependencies; privacy rules; code style; a no-key, no-internet test for every new behaviour; never hand-edit results files or loosen a pattern to pass; don't delete (use `_trash/`); never push; servers for tests use port 8010 and are stopped.

Different tonight:

**Two Pythons.** The chatbot uses `~/anaconda3/python.exe`. Document conversion uses the PDF environment, `~/.venvs/vnit-pdf/Scripts/python.exe` (Docling is installed there, per `requirements-pdf.txt`). Call it `PDFPY`. Check both exist in Step 0. If `PDFPY` is missing, don't install anything: mark Steps 1–3 `FAILED - PDF environment missing`, write the two setup commands from `requirements-pdf.txt` into REPORT10 for Shivanand, and go on to Step 4.

**Keys.**
- The Drive key is read by `drive_utils.load_key()` from `~/vnit-secrets.txt`. Let the code read it. Never `cat`, print, echo, log or commit it, and never use the Read tool on it.
- The Groq key is used **only in Step 5**, and in Step 6 only by the ablation runner, loaded inside the command: `GENAI_API_KEY=$(cat ~/groq-key.txt) ...`. Never printed. Everything else runs with `GENAI_API_KEY` unset.

**Network.** Steps 1–2 download from Google Drive and vnit.ac.in, politely, using the existing code (1 request a second for vnit.ac.in, which `ingest_documents.py` already does). Nothing else goes online.

**Baselines** (Step 0 re-measures; these are from the end of Runbook 9):

| Check | From `pipeline/` | After Runbook 9 |
|---|---|---|
| Agent unit tests | `$PY test_agentic.py` | 66/66 |
| Answer passage reaches the LLM | `$PY chunk_ranks.py` | 73/77 |
| Answer passage in top 3 | `$PY fact_ranks.py` | 14/18 |
| Right page in top 3 | `$PY evaluate.py` | Step 0 records it |
| End to end | `answer_check.json` | 97/100 saved results |

After Steps 3 and 4, every question that reached the LLM at baseline must still reach it, unless a trade is recorded with its reason (as Runbook 9 Step 3 did). One lost `fact_ranks` place is an acceptable trade; a lost `chunk_ranks` hit is not.

**Files that may change tonight:** `pipeline/`, `data/raw/doc_*.txt` (new ones), `data/documents/inventory.json` and `status.json` (only by **adding** entries; never remove or rewrite existing ones), `data/processed/` (rebuilt, not committed), the results files (only through `check_answers.py` and the ablation runner), docs. Read-only: `../vnit-website/` and its crawl, `data/raw_site_crawl/`, `data/feedback/`.

---

## Step 0. Baseline, tag and backups

1. `git status` must be clean after `24792b0`. Record it.
2. `git tag before-runbook-10`.
3. Back up `data/processed/index.pkl`, `chunks.jsonl`, `facts.db`, plus `data/documents/inventory.json` and `status.json`, to `~/vnit-chatbot-backups/2026-11-20-before-runbook-10/`. Check the sizes match.
4. Check `PY` and `PDFPY` exist, and that `$PDFPY -c "import docling"` works. Check `~/vnit-secrets.txt` exists **without reading it** (`test -s`).
5. Run the four no-key checks, save the summary lines and the per-question lists (`--verbose`) to `../_trash/r10_baseline_*.txt`.

**Done when:** tag and backups exist; Pythons, Docling and the key file are checked; the baseline table is in REPORT10.md.

---

## Step 1. Add the 116 documents to the inventory, from the saved crawl

**Idea.** `ingest_documents.discover()` can't be used as it is. It scans only the pages in `data/raw` (the first crawl's 81, not the pages where these 116 documents are linked), fetches every page live, and **rewrites `inventory.json` from scratch**. `count_new_documents.py` (Runbook 9) already finds the 116 offline, from the website crawl's saved HTML.

**Build.**
1. Add a `discover-crawl` action to `ingest_documents.py` (reuse, don't copy, the link rules from `discover()` and the selection from `count_new_documents.py`; move shared code into a small function both call):
   - Read `../vnit-website/crawl/manifest.json` and the saved `html/*.html.gz` (read-only). No page fetching.
   - Find document links by the same rules as `discover()`.
   - Keep only links that are **not** already in `inventory.json`, whose title isn't a list of people or procurement (`PEOPLE_LISTS`, `PROCUREMENT`), and whose title matches fees, calendar, hostel, scholarship, placement or rules, **and** isn't the same title as a document already read. This should reproduce Runbook 9's **116**. If the number differs, find out why and record it.
   - Fetch metadata exactly as `discover()` does: Drive metadata with `du.file_metadata` (key via `du.load_key()`), `modifiedTime` from the upload path for vnit.ac.in PDFs.
   - **Merge** into `inventory.json`: add new keys only, never change or drop existing ones. Write through a temporary file and rename, so a crash can't leave half a file.
   - Print: added, skipped by reason, metadata errors.
2. Run `$PDFPY ingest_documents.py plan` and save the output, so the order of conversion is visible. The new documents must land in tier 0 or 1 if they're fee, calendar or academic notices. If `select()` would put the Summer 2027 fee instructions in tier 2, record it but don't change the tiers.

**Tests (no key, no internet):** the merge keeps every existing entry unchanged and adds new ones; a link already in the inventory isn't added twice; a "merit list" title is skipped. Use a small fake manifest and a temp inventory.

**Done when:** `inventory.json` has the existing entries unchanged (compare keys and values against the backup in a script) plus about 116 new ones; the plan output is in REPORT10. Commit the code and `inventory.json`.

---

## Step 2. Convert them

1. Run the existing supervised conversion, **limited to the new documents**: `$PDFPY ingest_documents.py convert --tiers 0,1,2`. `convert` skips documents already in `status.json`, so it should only pick up new ones. Check that with `plan` first. If it would also retry old failures, add a `--only-new` flag that limits it to keys added in Step 1 (keep a list of them in `data/documents/added_2026-11-20.json`).
2. Run it in the background with a log: `... > ../_trash/convert.log 2>&1 &`. Poll the log every few minutes. It takes about 1 minute a document, longer for scanned ones. The supervisor already handles crashes and hangs. Don't babysit single documents.
3. Timebox: **4 hours**. If it isn't done by then, stop it cleanly (kill the supervisor; finished documents are kept, and a re-run carries on later), record how many are done, and continue with what's converted.
4. Then check the privacy filter worked: for every new `doc_*.txt`, `looks_like_personal_data` must be false (re-run it over them), and no new file contains a student roll number (`STUDENT_ROLL`). Move any that fail to `_trash/` and mark them excluded in `status.json` with the reason.

**Done when:** conversion finished or timeboxed; counts converted / excluded / failed / empty are in REPORT10, with 10 converted titles; the privacy re-check passes. Commit the new `data/raw/doc_*.txt`, `status.json` and any code change.

**If it goes wrong:** if the Drive API refuses (quota, 403), wait 15 minutes and retry once, then go on with what you have. If more than half the documents fail the same way, record the error message (with the key scrubbed, as `drive_utils` already does) and move on.

---

## Step 3. Rebuild and measure: keep only what helps

1. Rebuild in the background: `$PY chunk.py && $PY build_index.py && $PY build_facts.py`, logging to `../_trash/rebuild10.log`. Record the chunk count and the number of table rows in `facts.db`.
2. Run the four no-key checks and compare per question against Step 0.
3. **Decide.** Same rule as Runbook 9 Step 2: keep the new documents if no `chunk_ranks` hit is lost. If hits are lost:
   - find which new documents take the lost questions' places (look at what now ranks above the answer passage);
   - if they're **newer versions** of the same notice (for example a 2026-27 fee notice next to a 2025-26 one), that's expected, and maybe right: check whether the test's expected answer is now out of date. If the new document gives a different figure for the same thing, **don't change the test**: record it under "Tests that may be out of date" for Shivanand, with both documents' titles and figures;
   - otherwise move the documents that cost hits to `data/raw_new_docs_held/`, rebuild, and measure again.
4. Check that the new fee and calendar documents actually become searchable: for 5 of them, ask a question whose answer is clearly in them (pick it by reading the document, and write the expected pattern from the document's own text) through `chunk_ranks`' path, and record the rank. If they rank well, add those 5 as new cases in `check_answers.py`, each with the document named in a comment, following the existing style (the test set goes to 105). These are the questions Step 5 asks.

**Done when:** the decision and its numbers are in EXPERIMENTS-LOG §34, the kept index is on disk, and the 5 new cases are written. Commit.

---

## Step 4. The 3 table-row misses

Why each one fails (REPORT9 Steps 3 and 7):
- **Holi:** the gazetted list row "Holi — 04.03.2026" ranks 9th. Other chunks of the same holiday list fill that document's places **before** reranking, and the AI answered with "Holika Dahan — 03.03.2026" from the restricted list.
- **Companies:** "Number of Companies Visited — B.Tech: 121" is 64th before reranking. The reranker prefers the company-name list.
- **Ph.D. part-time:** the tuition row (₹15,000) ranks 10th, and the AI gave the ₹25,000 per-semester total.

`facts.db` already holds every one of these rows, and the `lookup_table` tool can find them. The agent just doesn't call it. Try these, **in this order**, measuring each with the four no-key checks and keeping only what doesn't lose a baseline hit:

1. **Table rows as corrective passages (code, no LLM call).** In the CRAG gate's corrective step in `respond.py`, when the topic is `fees`, `calendar` or `placement`, also add the best 2 `lookup_table` rows for the question (keywords from the question's rare words, slot filters from the question and profile, same scoring the tool uses) as corrective passages, through the same `evidence.add(..., origin="corrective")` path. Trace: "I also looked up matching rows in the documents' tables." Do this even when the grade is `correct`, but only for these three topics, and only rows that match at least 2 of the question's rare words. Check the extra ~150 tokens keep the first prompt under `planner.PROMPT_BUDGET`.
   - `chunk_ranks` runs `agent.answer`, which doesn't see corrective passages, so measure this one the way Runbook 9 did for the placements question: run the respond-path pieces with a fake LLM and check the expected figure is in the evidence. Write a small script `pipeline/evidence_check.py` that does this for all 77 fact questions, and report "answer in evidence" before and after. It needs no key.
2. **Look inside the best document (page-scoped re-ranking, from "Ideas not tried").** When the top reranked passage comes from a document whose table holds many rows, re-rank all of that document's chunks for the question (`query.retrieve_within`) and let its best 2 replace the weakest places. This is what fixes "other chunks of the same list fill its places before reranking".
3. **Row-level labels in the reranker input.** For table chunks, give the reranker `lead_in + row` text rather than the whole chunk, so "Number of Companies Visited" is judged on its own row.

Timebox: **2 hours** for all three together. Stop at the first combination that gets all 3 into the evidence without losing anything. Record every attempt, kept or not, in EXPERIMENTS-LOG §35, including the ones that didn't work.

**Tests (no key):** for each kept change, a test that the expected row reaches the evidence (with the real index, skipped when it's missing), and one that a question outside the three topics gets no table rows added.

**Done when:** each of the 3 is in the evidence or explained; `chunk_ranks` and `evidence_check` are no lower than after Step 3; tests pass. Commit.

---

## Step 5. Ask the AI: the 3, the new-document questions, regression

Budget: about 90,000 tokens on gpt-oss-120b. Stop early on a daily-limit message and list what's still waiting, with exact commands.

From `pipeline/`, one at a time, `GENAI_API_KEY=$(cat ~/groq-key.txt) $PY check_answers.py --only <name> --pause 30`:
1. The 3: `holiday_holi`, `companies_btech_2425`, `conv_phd_part_time`.
2. The 5 new-document cases from Step 3.
3. Regression, 8 cases covering what tonight changed: `placements`, `btech_fee` (a specific fee question), `hostel_fee_girls`, `msc_tuition`, `phd_tuition_full_time`, `midsem_slot_a`, `unanswerable_wifi`, `clarify_tuition_vague`.

If a regression case fails because of tonight's change, revert that change (with its tests and docs), rebuild if needed, re-run the case, and record it. Compute the new overall total from the saved results (for example "100/105").

**Done when:** all are asked or listed as waiting; the before/after table is in EXPERIMENTS-LOG §36.

---

## Step 6. Freeze the index and start the ablations

**Only if** Steps 3–5 ended with a kept, working index and no unresolved regression. Otherwise skip this step, mark it `SKIPPED` with the reason, and write the commands for Shivanand.

1. **Freeze.** `git tag final-index-2026-11-20`. Copy `index.pkl`, `chunks.jsonl` and `facts.db` to `~/vnit-chatbot-backups/final-index-2026-11-20/`. Write in EXPERIMENTS-LOG §26 that every ablation row from now on uses this index, and why the older rows are set aside.
2. **Set the old results aside**, as REPORT9 Step 8 says: move every `data/processed/answer_check_*.json` (the per-configuration files) into `data/processed/results-before-2026-11-20/`, so the runner measures afresh instead of reusing old answers. Follow REPORT9's exact commands. Also **copy** (not move) `answer_check.json` there, so the 97/100 record and tonight's Step 5 answers are kept. If the runner's final full run also reads `answer_check.json` and would skip questions already answered, make sure the final full run writes to its own config file instead, so the headline number is a fresh run on the frozen index. Check `run_ablations.sh` and `check_answers.py --config` to confirm, and record what you found.
3. **Start the runner in its own window**, so it keeps going after this session ends. From Git Bash:
   `cmd //c start "VNIT ablations" "C:\Program Files\Git\bin\bash.exe" -lc "cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-chatbot/pipeline && bash run_ablations.sh"`
   (check the Git path first; it may be under `AppData\Local\Programs\Git`). Wait 2 minutes and check `data/processed/ablation_runs.log` shows it started. If it can't be started that way, don't keep trying: write the command for Shivanand.
4. Don't touch the index, `data/raw` or retrieval code after this step. Step 7 only edits docs.

**Done when:** the tag and frozen copy exist, the old results are set aside, and the runner is confirmed started (log line) or the command is handed over.

---

## Step 7. Docs and the morning report

1. README ("Project status", "Measured quality", corpus numbers: pages, documents, chunks, table rows, test count), APPLICATION.md and HOW-TO-RUN.md (add how to run `discover-crawl`, in the same plain style as the existing document-refresh section).
2. Check the website still works with the new index (no key, port 8010): `/site/` loads and `/ask` answers. Record it.
3. **REPORT10.md "Good morning" at the top**, in plain words:
   - the score before and after (97/100 → ?/105), and the no-key numbers before and after;
   - how many documents were added and kept, and the 5 most useful;
   - which of the 3 table-row misses are fixed, and why not for any that aren't;
   - "Tests that may be out of date", if any, with both figures;
   - whether the ablations are running: the log line, when they should finish (about 3–4 days), and how to check (`tail data/processed/ablation_runs.log`, then `python ablation_table.py` when it says "all tracks done"); **while they run, the free allowance is mostly theirs**, so demo with care or pause them by closing their window (re-running the command resumes);
   - what to do next: slides 13–19 once the table is filled, and `git push` (exact command; it triggers the Hugging Face workflow, which skips without `HF_TOKEN`).

**Done when:** docs updated, PROGRESS-10.md has every step marked, last commit in.

---

## Don't do

- Don't ask questions or wait for answers.
- Don't run `discover()` (it rewrites the inventory from the first crawl's pages). Use `discover-crawl`.
- Don't remove or rewrite existing entries in `inventory.json` or `status.json`.
- Don't print or read the keys, or use the Groq key outside Steps 5 and 6.
- Don't change a test's expected answer because a newer document disagrees; record it.
- Don't special-case questions, pages or facts in code, or loosen patterns.
- Don't change the index or retrieval after Step 6's freeze.
- Don't edit `../vnit-website/`. Don't delete, don't push.
