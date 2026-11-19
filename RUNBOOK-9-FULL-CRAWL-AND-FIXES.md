# Runbook 9: the full crawl in the chatbot, and the last 9 failures

**For:** Claude Code, running unattended overnight on Shivanand's Windows laptop (the VS Code extension, as for Runbook 8), in `FYP\VNIT-Website-Chatbot\vnit-chatbot`.
**Why:** the 100-case check ended at **91/100** (commit `dd2ce2a`). Of the 9 failures, 5 happen because search never brings the answer to the AI, and 4 are mistakes in when to ask back and how the profile is used (EXPERIMENTS-LOG §27). Meanwhile Runbook 8 crawled **1,628 pages** of vnit.ac.in for the website (`../vnit-website/crawl/`), and the chatbot still searches only the **81 pages** of the first crawl, plus the documents. Tonight the chatbot gets the full crawl, the ask-back logic is fixed, and only at the end the AI is asked the failing questions again.
**Owner:** Shivanand directs and is a beginner at app building. He is asleep while this runs. In the morning he reads the "Good morning" section of `REPORT9.md`, so it must say in plain words what improved, what didn't and what to do next.

---

## How this runbook is run

One Claude Code session, started with:

> Read RUNBOOK-9-FULL-CRAWL-AND-FIXES.md and PROGRESS-9.md (if it exists). Do every step from the first one not marked in PROGRESS-9.md through Step 8, in order, without stopping between steps, following "Ground rules". After each step: run its "Done when" checks, write the results into REPORT9.md, mark the step in PROGRESS-9.md, and commit. Never ask a question.

If the session is compacted or restarted, PROGRESS-9.md is the memory: read it first and carry on from the first unmarked step.

| Step | What | Rough time | Groq quota |
|---|---|---|---|
| 0 | Baseline, tag and backups | 30 min | none |
| 1 | Convert the full crawl into `data/raw` | 1.5 h | none |
| 2 | Rebuild the index and measure: keep it only if better | 2 h | none |
| 3 | The 5 search misses | 2 h | none |
| 4 | Ask back only when it changes the answer | 2 h | none |
| 5 | The two failing conversations | 1 h | none |
| 6 | New documents linked from the new pages (count only) | 30 min | none |
| 7 | Ask the AI: the 9 failures and a regression sample | 1.5 h | ~120k tokens |
| 8 | Docs and the morning report | 45 min | none |

---

## Ground rules (every step)

**Never stop to ask.** Nobody is awake. When something is unclear, pick the option that is smallest, safest and easiest to undo, write it under "Decisions" in `PROGRESS-9.md` with one line of reasoning, and carry on.

**When a step fails.** If "Done when" fails and the step's "If it goes wrong" notes don't fix it within its timebox, revert that step's files (`git checkout -- <files>`, or restore from Step 0's backup for the index), write what happened in REPORT9.md, mark the step `FAILED` with the reason in PROGRESS-9.md, and go on to the next step. A later step that depended on it does the version that doesn't, and says so.

**Environment.** Same as Runbook 7. In Git Bash:
```
PY=~/anaconda3/python.exe
cd pipeline
```

**Groq quota: only in Step 7.** Steps 0–6 and 8 run with `GENAI_API_KEY` unset (`env -u GENAI_API_KEY ...` where in doubt). In Step 7 the key is loaded inside the command that needs it, `GENAI_API_KEY=$(cat ~/groq-key.txt) $PY check_answers.py ...`, and is never printed, echoed, logged, written to a file or committed. Don't use the Read tool on the key file.

**Don't break what works.** Baselines (Step 0 re-measures them):

| Check | Command (from `pipeline/`) | Last known | Needs key |
|---|---|---|---|
| Agent unit tests | `$PY test_agentic.py` | 54/54 | no |
| Answer passage reaches the LLM | `$PY chunk_ranks.py` | 41/47 of the answerable single questions (README) | no |
| Answer passage in top 3 | `$PY fact_ranks.py` | Step 0 records it | no |
| Right page in top 3 | `$PY evaluate.py` | Step 0 records it | no |
| End to end | `check_answers.py` | 91/100 saved results | yes |

After every step from 1 on, run the four no-key checks and record them in a running table in REPORT9.md (one row per step). **Every question that reached the LLM at baseline must still reach it**, unless the step's notes say a trade is allowed and the trade is recorded. Never run the full `check_answers.py` (about 450k tokens). Use `--only <fragment>` with `--pause 30`, and only in Step 7.

**General fixes, not special cases.** No code that names a test question, a page or a fact. A fix must be a rule that would also help a question nobody wrote yet. If the only fix is a special case, don't make it: record the miss honestly.

**No new LLM calls in the live path, and no new dependencies.** Same as Runbook 7: grading, routing, ask-back and filtering are plain code.

**Privacy.** Pages that are lists of people (candidates, seating plans, merit lists, committee lists with phone numbers) stay out of `data/raw`, using the same rules as the documents (`ingest_documents.looks_like_personal_data` and the title filters in that file). The faculty recruitment shortlist stays out.

**Code style (Shivanand's preference).** A docstring saying *why* each module exists, short functions, plain names, comments only where the reason isn't obvious, no banner comments, no "Step N" comments, no emojis.

**Tests.** Every new behaviour gets a no-key, no-internet test in `pipeline/test_agentic.py`, in the existing style. Update the test count wherever the docs mention it.

**Files.**
- Read-only: `../vnit-website/` (including its crawl), `data/feedback/`, every `answer_check*.json` except through `check_answers.py` itself (never hand-edit results), `run_ablations.sh` and its log.
- Don't delete files. Move unwanted ones to `_trash/` (add it to `.gitignore`).

**Git.** Commit after every step in this repo, with a short plain message in the existing style. `git status` before each commit; stage files by name or by folder (`git add pipeline/ data/raw/`), never `data/processed/index.pkl`, `chunks.jsonl` or `facts.db` (they're in `.gitignore`, so check). Never push.

**Docs after every step.** A new EXPERIMENTS-LOG section for each step that changes behaviour (§28 for Step 1, §29 for Step 2, and so on), with what changed, before/after numbers and anything rejected. REPORT9.md gets a section per step with the commands, trimmed outputs and "Done when" results.

**Processes.** A server started for a test uses port 8010 and is stopped before the step ends. Anything that might hang runs under `timeout`. The index build may take a long time on the larger corpus: run it in the background writing to a log file, and poll the log, rather than letting one command time out.

---

## Step 0. Baseline, tag and backups

1. `git status` must be clean (it was after `4755346`). If it isn't, record what's dirty and commit only if it's obviously the 100-case run's results; otherwise leave it and note it.
2. `git tag before-runbook-9`.
3. Back up `data/processed/index.pkl`, `chunks.jsonl` and `facts.db` to `~/vnit-chatbot-backups/2026-11-20-before-runbook-9/`. Check the copies' sizes match.
4. Run the four no-key checks. Save each one's summary line, **and** the per-question lists (`chunk_ranks.py --verbose` to `../_trash/baseline_chunk_ranks.txt`, and the same for the others if they have a verbose mode), so later steps can see exactly which questions moved.
5. From `data/processed/answer_check.json`, list the 9 failing cases with their saved answer and trace (trimmed) in REPORT9.md under "The 9 failures". This tells Steps 3–5 what actually went wrong.

**Done when:** the tag and backups exist, and the baseline table and the 9 failures are in REPORT9.md.

---

## Step 1. Convert the full crawl into `data/raw`

**Idea.** `../vnit-website/crawl/` has `manifest.json` (URL → `{file, fetched, final_url, status}`) and `html/*.html.gz`. The chatbot reads plain text files with a header. Turn each new page into the same format the first crawl used, with the same text extraction, so the new pages look like the old ones to the chunker.

**Build `pipeline/import_site_crawl.py`.**
1. Read `pipeline/fetch_utils.py` first. If HTML-to-text is inside `fetch_page`, move it into its own function `html_to_text(html) -> (title, text)` and have `fetch_page` call it, **with no change in behaviour**: re-extract 5 of the old pages' HTML if cached anywhere, or at least run `test_agentic.py` and check one live-format sample by eye.
2. For each manifest entry with status 200:
   - **Skip URLs already in `data/raw`** (compare normalised `SOURCE_URL`s: lower-case host, no trailing slash, no `#fragment`, percent-encoding normalised). The old files stay as they are, because the 100 test cases were checked against them. Count how many overlap.
   - Skip what `crawl.should_skip` skips, plus: pagination and archive pages (`/page/<n>/`, `/tag/`, `/author/`, `?replytocom=`), attachment pages, feeds, and search pages.
   - Extract with `html_to_text`. Skip pages under 40 words, pages that are mostly Devanagari (over 50% of letters; the documents' Hindi-only rule), and pages `looks_like_personal_data` flags or whose title matches the document title filters.
   - Skip exact duplicate bodies (hash of the whitespace-normalised text, against both old and new files); keep the shortest URL.
   - Write `data/raw/site_<slug>.txt` with `SOURCE_URL`, `TITLE`, `FETCHED` (from the manifest) and `CRAWL: full-2026-11-19`, then `---` and the text. Use `crawl.slugify` for the slug, and add a numeric suffix if two slugs collide.
3. Print and save to REPORT9: counts of imported, overlapping, and skipped by reason, plus 10 random imported titles and 10 random skipped titles with their reasons, so the filters can be checked by eye.
4. **Look at 15 imported files** (head of each) and fix the filters if menus, cookie notices or footers dominate them. If the 40%-of-pages boilerplate idea from Runbook 8 helps here, apply it to the new files only.

**Done when:** the import runs cleanly; every imported file has the header; the counts are recorded; `test_agentic.py` passes; the no-key checks are **unchanged** (the index hasn't been rebuilt yet, so they must be identical). Commit the script and `data/raw/site_*.txt`.

**If it goes wrong:** if the extraction gives very different text from the old pages for the same URL (compare 3 overlapping URLs, old file versus fresh extraction), use the old crawler's exact extraction anyway and record the difference. Don't build a second extractor.

---

## Step 2. Rebuild the index and measure: keep it only if better

**Idea.** About 20 times more pages can help (answers that were never in the index) or hurt (near-duplicate pages crowding out the right passage). Measure it; don't assume.

1. Rebuild in the background, logging: `$PY chunk.py && $PY build_index.py && $PY build_facts.py > ../_trash/rebuild.log 2>&1 &`. Poll until done. Record the chunk count, the time taken and the index size.
2. Run the four no-key checks. Compare per question against Step 0's lists.
3. **Decide:**
   - **Keep** if the number of answerable questions whose passage reaches the LLM (`chunk_ranks`) is higher than at baseline, *and* no more than 1 baseline hit is lost across all checks, *and* that one is listed with the reason.
   - **Otherwise try, in this order, up to the 2-hour timebox:**
     a. Leave out low-value page types: news posts and event pages older than 2 years, gallery pages, pages whose text is mostly links (link text over 60% of the words).
     b. Give `chunk.py` a `CRAWL` field in each chunk's metadata, and in `query.py`, when two chunks have near-identical text (an existing near-duplicate check, or Jaccard over word 5-grams above 0.8), keep the one from the first crawl. This stops new copies of old pages displacing the passages the tests were checked against.
     c. If retrieval has a per-page cap on candidates, check it still makes sense with more pages.
     Re-measure after each one.
   - **If none of these gets there:** restore the backup index, move the imported files that cause trouble to `_trash/`, keep only those that help or are neutral (for example only the pages of sections the old crawl never reached), rebuild, and measure again. If even that doesn't help, restore the backup, keep `site_*.txt` out of `data/raw` (move them to `data/raw_site_crawl/`, which `chunk.py` doesn't read), and record the full result. That is a real finding for the report, not a failure.
4. Also run `chunk_ranks.py` (or the same path) on the **5 search misses** by name and record where each answer passage now ranks.

**Done when:** the decision and its numbers are in EXPERIMENTS-LOG §29, and the index on disk is the kept one. Commit code changes (the index itself is not committed).

---

## Step 3. The 5 search misses

The misses (§27): when higher-semester classes start (21 July), the Holi holiday (4 March), PhD full-time tuition (₹7,500 a semester), how many companies came for B.Tech in 2024-25 (121), and who can stand for General Secretary (4th-year students). Some cases in the failure list have slightly different names (`holiday_holi`, `phd_tuition_full_time`, `companies_btech_2425`); find each case in `check_answers.CHECKS` by its expected pattern.

For each one still missed after Step 2, timeboxed at 25 minutes:
1. `grep` `data/raw` for the expected answer to find the passage that holds it. Note the file, and whether it is a table row (` | `).
2. Run it through `agent.answer` / `chunk_ranks --verbose` and see where that passage ranks, and what beats it.
3. Find the **general** cause and fix that. Likely kinds:
   - The answer is in a table row whose chunk lacks the words the student uses ("holiday" in the heading but not on the row). Fix: carry the table's lead-in or heading into each row's chunk text in `chunk.py` (as `build_facts.py` already does for `lead_in`).
   - A short student word isn't matched ("phd" versus "Ph.D.", "btech" versus "B. Tech."). Fix: extend the normalisation in `programme_terms.py` or the query rewrite that already handles programmes.
   - The answer is in `facts.db` but the planner never calls `lookup_table`, and the first search misses it. Fix: in the CRAG gate's corrective step, when the topic is `fees` or `calendar`, also add the top `lookup_table` rows for the question's slots as corrective passages (code, no LLM call; same evidence format as the existing corrective passages).
4. After each fix, re-run the four no-key checks. A fix that costs a baseline hit is reverted.

**Done when:** each of the 5 is either fixed (reaches the LLM in `chunk_ranks`) or recorded with why not, the no-key checks are no lower than after Step 2, and EXPERIMENTS-LOG §30 is written.

---

## Step 4. Ask back only when it changes the answer

The three clarify failures (§27, and their saved traces from Step 0):
- **Asks when it shouldn't:** "when can first year students join the hostel mess?" gets a programme question, although the answer (from the day they report) is the same for everyone.
- **Doesn't ask when it should:** "what is the tuition fee?" is answered without asking which programme.
- **Profile not used enough:** "hostel fee for first year?" with profile M.Tech / boys doesn't bring the M.Tech fee sheet (₹40,080) to the AI.

Fixes, in `slots.py` and where it's called in `respond.py`:
1. **Ask only when the answers differ, not only the documents.** In `needs_clarification`, the documents differing on a slot is not enough. Ask only when the top passages for different slot values also carry **different figures or dates** relevant to the question (compare the numbers and dates in each value's best passage: if they're all the same, or none has any, don't ask). This is what tells "mess joining date" (same for everyone) from "hostel fee" (different per programme).
2. **Intent should also come from the words, not only the topic.** "Tuition fee" with no programme named must clarify on programme. Check why it doesn't: probably `REQUIRED["fees"]` needs `programme` and `category`, but the passages for "tuition fee" are all one programme's sheet, so they "agree". Fix generally: for `fees`, when the question names no programme and the corpus has fee documents for **2 or more programmes** (from `facts.db` or document titles, computed once at startup), ask, even if the top 7 passages happen to agree.
3. **Use the profile in the search, not only in the wording.** `apply_profile` appends "(for M.Tech boys)" to the question, but the programme filter in retrieval may only read programmes from the original text. Make sure retrieval's programme/gender filters get the profile's values directly (pass them through `respond.answer` → `agent.answer` / `query.retrieve` as explicit filters), so "hostel fee for first year?" with M.Tech / boys searches only M.Tech boys' sheets.
4. Re-check the earlier rule: **none of the original 39 questions may ask back** (Runbook 7 Step 3's "0 clarifications" check), and none of the 77 fact questions in the 100 should either, unless the case itself expects it. Run all 100 through `respond.answer` with no key and count `mode == "clarify"`; list any unexpected ones and tighten until there are none.

**Tests:** the three cases above as no-key tests (mode and choices, or the M.Tech sheet among the passages); the "0 unexpected clarifications over all 100" count as a test that's skipped when the index is missing.

**Done when:** the tests pass, `clarify_*` and `mess_joining_first_year` behave correctly in the no-key path (record mode, choices and top passages), the no-key checks are no lower than after Step 3, and EXPERIMENTS-LOG §31 is written.

---

## Step 5. The two failing conversations

`conv_hostel_mtech` and `conv_phd_part_time` fail (two-turn cases: a first question, then "and for part time?" or similar). From their saved traces (Step 0):
1. Find whether the failure is in the **rewrite** (`followup.py` produced the wrong stand-alone question), in **retrieval** (right question, wrong passages) or in the **answer** (right passages, wrong answer).
2. Fix the cause generally:
   - **Rewrite:** `followup.py` uses gpt-oss-20b. Add a code-only fast path *before* the LLM rewrite for the common pattern "and for <slot value>?" / "what about <slot value>?": take the previous question, swap the slot value of the same kind (programme, gender, category, study year, full-time/part-time), and skip the LLM call. That is cheaper and repeatable. Add `part-time`/`full-time` as a slot (`mode_of_study`) if it isn't one, with the same validator rules.
   - **Retrieval:** usually Step 4.3's fix (explicit filters) covers it once the rewritten question names the programme.
   - **Answer:** record it for Step 7.
3. Test the fast path without a key on 8 phrasings ("and for girls?", "what about M.Tech?", "and part time?", "for SC students?"), plus 2 that must **not** take it ("and the mess fee?", "who is the warden?").

**Done when:** the tests pass, the two conversations get the right stand-alone question in the no-key path (record it), the no-key checks are unchanged, and EXPERIMENTS-LOG §32 is written.

---

## Step 6. New documents linked from the new pages (count only)

The new pages may link Google Drive PDFs the chatbot has never converted. Converting them needs the Drive key and Docling, and takes hours, so **tonight only counts them**:
1. Run the discovery part of `ingest_documents.py` (read it first: `discover()` / `_page_urls()`) against the pages now in `data/raw`, **without downloading or converting**. If discovery can't run without the Drive key, write a small read-only scan that finds `drive.google.com/file/d/<id>` and `.pdf` links in the imported HTML instead.
2. Report in REPORT9: how many new document links, how many already in `inventory.json`, and the 20 most promising by title (fees, calendar, hostel, scholarship, placement, rules), so Shivanand can decide whether a conversion run is worth it.
3. Don't change `inventory.json` or `status.json`.

**Done when:** the counts and the list are in REPORT9.md.

---

## Step 7. Ask the AI: the 9 failures and a regression sample

Only now is the key used. Budget: about 120,000 tokens on gpt-oss-120b, well under a day's 200,000, leaving the rest for Shivanand's demo.

1. `cd pipeline`, then for each of the **9 failing cases**, by name, one at a time:
   `GENAI_API_KEY=$(cat ~/groq-key.txt) $PY check_answers.py --only <name> --pause 30`
2. Then a **regression sample** of 10 that passed before, chosen to cover what tonight changed: `director`, `hostel_fee` (a specific one), `btech_fee`, `placements`, `unanswerable_wifi`, `conv_hostel_girls`, `clarify_hostel_vague`, `clarify_then_answer`, `no_clarify_director`, and one calendar question. Use `--only` with each name's exact fragment.
3. If a run reports the daily limit (429 / limit reached), stop asking. Record which ones are still waiting, and write the exact commands for Shivanand to finish them tomorrow.
4. Record each result: PASS/FAIL, mode, tool calls, verifier verdict, and for a FAIL the answer's first 300 characters and why it failed.
5. **If a regression case now fails**, look at its trace. If tonight's change caused it, revert that change (tests and docs too), rebuild if needed, and re-run that one case. Never make a pattern in `check_answers.py` looser to turn a fail into a pass; change a pattern only when the saved answer is right according to the document, and say which document.
6. Run `$PY check_answers.py --rescore` only if a pattern was changed, and record why.

**Done when:** every case in 1 and 2 has been asked (or is listed as waiting for quota), the new overall count is computed from `answer_check.json` (for example "96/100 saved results"), and EXPERIMENTS-LOG §33 has the before/after table.

---

## Step 8. Docs and the morning report

1. Bring `README.md` ("Project status", "Measured quality", the corpus numbers: pages, documents, chunks, table rows), `APPLICATION.md` and `HOW-TO-RUN.md` up to date. Stale numbers are worse than none.
2. **Ablations note.** The ablation rows in EXPERIMENTS-LOG §26 were measured on the old index. Write in §26 that the corpus changed on 20 Nov, and that the table must be re-run on the new index for the report to compare like with like. **Don't start `run_ablations.sh`.** Write in REPORT9 the exact commands for Shivanand to start it in the morning, and how long it takes (about 3–4 days of free quota for all rows plus a full run). Mention the option of running only the two missing rows on the old index from the Step 0 backup if the report deadline is close.
3. **Website:** the site in `../vnit-website` doesn't need rebuilding. Check that `start_website.bat` still starts and `/site/` and `/ask` still work with the new index (no key, port 8010), and record it.
4. **REPORT9.md, "Good morning" at the top**, in plain words:
   - the score before and after (91/100 → ?), and the no-key numbers before and after;
   - which of the 9 failures are fixed, and the honest reason for each one that isn't;
   - what the full crawl added (pages, chunks) and whether it was kept;
   - anything that got worse, and what was done about it;
   - the 3 things to do next, in order: restart the ablations (exact command), decide on converting the new documents (Step 6's numbers), and update slides 13–19 with the new numbers;
   - `git push` when he's happy (exact command), noting it triggers the Hugging Face workflow, which skips without `HF_TOKEN`.

**Done when:** all docs are updated, PROGRESS-9.md has every step marked, and the last commit is in.

---

## Don't do

- Don't ask questions or wait for answers.
- Don't use the key outside Step 7, print it, or run the full `check_answers.py`.
- Don't hand-edit results files, or loosen a test pattern to make something pass.
- Don't special-case test questions, pages or facts in code.
- Don't add LLM calls to the live path, frameworks, or dependencies.
- Don't replace the old crawl's files with the new crawl's versions of the same URLs.
- Don't convert documents tonight, or change `inventory.json` / `status.json`.
- Don't start, stop or edit `run_ablations.sh`.
- Don't edit `../vnit-website/`.
- Don't delete files, and don't push.
