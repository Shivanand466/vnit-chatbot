# Runbook 9 report: the full crawl in the chatbot, and the last 9 failures

## Good morning

**In short: the chatbot now gets 97 of 100 test questions right (it was 91).** Six of the nine failures are fixed, by changes that are general rules rather than special cases. The eleven questions that passed before still pass. All of it is committed; nothing is pushed.

**Before and after**

| | Before (Runbook 9 start) | After |
|---|---|---|
| Answer check, saved results | 91/100 | **97/100** |
| Answer passage reaches the AI (`chunk_ranks`, no key) | 69/77 | **73/77** |
| Answer passage in the top 3 (`fact_ranks`) | 15/18 | 14/18 (one moved from 3rd to 4th, still reaches the AI) |
| Right page in the top 3 (`evaluate`) | 16/19 | 16/19 |
| Automated tests (`test_agentic`, no key) | 54/54 | **66/66** |

**The nine failures**

| Case | Now | What fixed it, or why not |
|---|---|---|
| M.Sc tuition | ✅ | Table rows were drowned by a 40-word heading repeated on every row; now the heading is written once per group, so the right row reaches the AI |
| Ph.D. full-time tuition | ✅ | Same fix: the ₹7,500 tuition row now reaches the AI (it gave the ₹22,100 total before) |
| Mess joining (asked "boys or girls?" for nothing) | ✅ | The chatbot now asks back only when the groups' answers have different figures or dates |
| "what is the tuition fee?" (didn't ask which programme) | ✅ | When fee sheets for 3 or more programmes match, it asks |
| "what about mtech?" after a hostel-fee question | ✅ | Follow-ups that only change a detail (programme, boys/girls, category, year, full/part-time) are rewritten in plain code; the AI rewrite had left it as "What about M.Tech?" |
| Hostel fee with the profile M.Tech/boys | ✅ | The profile already reached the search; with cleaner passages the AI now gives ₹40,080 |
| Holi holiday | ❌ | The row "Holi — 04.03.2026" is one row of a long table and still ranks 9th; the AI answered from the restricted list (Holika Dahan, 3 March) |
| Companies at B.Tech placements 2024-25 (121) | ❌ | The statistics row is never found, not even when the agent looks inside the report; the company-name list outranks it |
| Ph.D. part-time tuition after a follow-up | ❌ | The follow-up is now read correctly, but the ₹15,000 tuition row ranks 10th, so the AI gave the ₹25,000 total |

**The full crawl (1,628 pages from the website project): measured, not kept.** 814 usable pages were imported (lists of people, near-empty pages, image pages and duplicates left out), and the index was rebuilt three ways. None brought a tested answer to the AI, and each pushed some right answers out, because dozens of new pages have titles like "… – Training & Placement Department" that compete with the page that has the real figures. The pages are kept in `data/raw_site_crawl/` (not searched), so trying again later costs one rebuild. The tested answers are all in documents, not in those pages (EXPERIMENTS-LOG §29).

**What got worse, and what was done:** only `fact_ranks` dropped by one (an exam-date passage moved from 3rd to 4th, behind three passages of the same exam schedule; it still reaches the AI). Kept, because the same change brought four other answers to the AI. Recorded in PROGRESS-9.md, Decisions. Everything tried and rejected is in EXPERIMENTS-LOG §29-§30.

**Quota used:** about 99,000 tokens of gpt-oss-120b (20 questions), so roughly half of today's allowance is left for a demo.

**The 3 things to do next, in order**

1. **Restart the ablation measurements on the new search** (the old rows were measured before tonight's changes, and three rows were never finished). In Git Bash:
   ```
   cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-chatbot
   mkdir -p _trash/ablations-before-20-nov
   mv data/processed/answer_check_oneshot.json data/processed/answer_check_no_tools.json data/processed/answer_check_agent_30oct.json data/processed/answer_check_crag.json _trash/ablations-before-20-nov/
   cd pipeline
   bash run_ablations.sh
   ```
   Moving the old files matters: the script resumes, so it would otherwise keep the old answers. It runs on its own for **about 3-4 days** of free allowance (all rows plus one full run of 100). Keep the laptop on; if it stops, run `bash run_ablations.sh` again. When the log says "all tracks done", run `python ablation_table.py`.
   *If the report deadline is close:* the two missing hard-set rows can instead be finished on the old search, in a separate copy so nothing here changes: `git worktree add ../vnit-chatbot-old before-runbook-9`, copy the three files from `~/vnit-chatbot-backups/2026-11-20-before-runbook-9/` into `../vnit-chatbot-old/data/processed/`, copy the four old `answer_check_*.json` files there too, and run `bash run_ablations.sh` in `../vnit-chatbot-old/pipeline` (about a day). The table then compares like with like, on the old search.
2. **Decide whether to convert the new documents.** The full crawl links **116 documents the chatbot has never read** about fees, calendars, hostels, scholarships and placements, including the Summer 2027 fee instructions, the 2026-27 scholarships and the January 2027 Ph.D. admission brochure (list in Step 6 below). Converting them takes about 2-4 hours and the Drive key (`ingest_documents.py discover`, then `convert`, then rebuild).
3. **Update slides 13-19** with the new numbers: 97/100, 73/77, 66/66 tests, and the full-crawl finding.

**When you are happy, push:** `cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-chatbot && git push`. It triggers the Hugging Face workflow, which skips itself because no `HF_TOKEN` is set.


## No-key checks after each step

| After step | test_agentic | chunk_ranks: reaches LLM (top 7) | top 3 | top 12 | fact_ranks top 3 | evaluate top 3 |
|---|---|---|---|---|---|---|
| 0 (baseline) | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |
| 1 (files added, index not rebuilt) | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |
| 2 (bigger index measured, not kept; backup restored) | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |
| 3 (shared table lead-ins, repeated passages dropped) | 57/57 | 73/77 | 66/77 | 74/77 | 14/18 | 16/19 |
| 4 (ask back only when the answers differ) | 63/63 | 73/77 | 66/77 | 74/77 | 14/18 | 16/19 |
| 5 (slot-only follow-ups rewritten in code) | 66/66 | 73/77 | 66/77 | 74/77 | 14/18 | 16/19 |
| 6 (count only, no search change) | 66/66 | 73/77 | 66/77 | 74/77 | 14/18 | 16/19 |

## Step 0. Baseline, tag and backups

- `git status`: clean apart from the untracked runbook and `.claude/` (local editor settings, left alone). The runbook is committed with this step.
- `git tag before-runbook-9` at `4755346`.
- Backups in `~/vnit-chatbot-backups/2026-11-20-before-runbook-9/`, sizes match the originals: `index.pkl` 34,507,470 bytes, `chunks.jsonl` 9,310,382, `facts.db` 8,753,152.
- Per-question baseline lists: `../_trash/baseline_chunk_ranks.txt` (`--verbose`), `baseline_fact_ranks.txt`, `baseline_evaluate.txt`, `baseline_test_agentic.txt`.

Answer passage not reaching the LLM at baseline (chunk_ranks, 8 of 77): `placements` (not in top 12), `msc_tuition` (not in top 12), `barch_tuition` (rank 9), `higher_sem_classes_start` (not in top 12), `holiday_holi` (rank 8), `phd_tuition_full_time` (rank 10), `companies_btech_2425` (not in top 12), `gs_eligibility` (not in top 12).

evaluate.py misses (3 of 19): placements 2025-26 (a Drive document beats the T&P page), CSE established (the CSE brochure PDF beats the department page), scholarships for girls (a Drive document beats the notice page).

**Done when:** tag and backups exist; baseline table and the 9 failures are below. **Met.**

## The 9 failures

From `data/processed/answer_check.json` (91/100), answers and traces trimmed.

### `msc_tuition`
- **Question:** What is the yearly tuition fee for M.Sc students at VNIT?
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `15,?000`
- **Answer (trimmed):** **Yearly tuition fee for M.Sc. students: ₹0 (no tuition fee).**  - The 2‑year fee estimate for SC/ST M.Sc. students lists “Tuition Fee – First Year: NIL; Second Year: NIL”[1].  **Note:** This figure is provided only for SC/ST category students; the fee for Open/EWS categories is not shown in the available documents.
- **Sources:** 1
- **Trace:** A question about VNIT: looking it up. / Topic: fees. / Searched VNIT's pages and documents: 7 passages from 4 sources. / The first search looked weak (the top passages do not mention “yearl”), so I also looked inside “Notice No. 3266 dated 17 November 2025 Regarding Hostel Fee payment information for Summer 2025 for all UG – M.Sc. students / Wrote the answer from the first search; no further lookups were needed. / No figures, dates or contact details to check in this answer.

### `holiday_holi`
- **Question:** is holi a holiday at vnit in 2026? which date?
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `0?4[./-]0?3|\b4(th)?\s*Mar|Mar\w*\s*4\b`
- **Answer (trimmed):** **Holi is not listed as a holiday for 2026; only Holika Dahan (the day before Holi) appears on 03 March 2026 (Tuesday).**[1]  - The official “List of Restricted Holiday’s during the year 2026” mentions **Holika Dahan – 03‑03‑2026 (Tuesday)** but does not include a separate entry for Holi.  Note: Holi is traditionally c
- **Sources:** 2
- **Trace:** A question about VNIT: looking it up. / Topic: calendar. / Searched VNIT's pages and documents: 6 passages from 4 sources. / The first search looked weak (the top passages do not mention “holi”), so I also looked inside “Extension of the Last Date for filling the Course Feedback”. / Searched for “Holi 2026 VNIT holiday”: Visvesvaraya National Institute of Technology (VNIT), Nagpur; 🎓 VNIT Nagpur | 24th Convocation 2026 / Looked up table rows for “Holi” (2026-27): 8 rows from ACADEMIC CALENDAR (Winter 2026) for First Year UG (B.Tech/B.Arch); ACADEMIC CALENDAR (Winter 2026) for First Year PG (M.Tech/M.Sc/MBA); ACADEMIC CALENDAR (Winter 202 / Wrote the answer after 2 round(s) of tool use. / Checked 5 figure(s) against the sources: all found. / I couldn't find this in VNIT's documents, so I've added who to contact.

### `phd_tuition_full_time`
- **Question:** phd full time tuition fee per semester?
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `7,?500`
- **Answer (trimmed):** **₹22,100 per semester** for a full‑time Ph.D. programme[1].  - The Ph.D. (Full‑Time) per‑semester tuition fee is listed as ₹22,100 in the 2026‑04‑09 fee structure document.  Note: This amount applies to Indian national students; international (NRI/foreign) fees are quoted separately in USD.
- **Sources:** 1
- **Trace:** A question about VNIT: looking it up. / Topic: fees. / Searched VNIT's pages and documents: 7 passages from 4 sources. / The first search looked relevant (score 6.4). / Wrote the answer from the first search; no further lookups were needed. / Checked 3 figure(s) against the sources: all found.

### `companies_btech_2425`
- **Question:** how many companies came for btech placements in 2024-25
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `\b121\b`
- **Answer (trimmed):** I’m sorry, but none of the provided passages give a total count of companies that visited for B.Tech. placements in 2024‑25. They list many individual companies (e.g., Axis Bank, Axxela Research & Analytics, Azure Power India, etc.) but do not state an overall number.  You could look at the complete “Placement and Inte
- **Sources:** 0
- **Trace:** A question about VNIT: looking it up. / Topic: placement. / Searched VNIT's pages and documents: 6 passages from 3 sources. / The first search looked weak (the top passages do not mention “btech”); no better-titled page had a relevant passage, so I continued with what it found. / Searched for “Placement and Internship Report 2024-2025 total companies visited B.Tech”: Placement and Internship Report 2024-2025 / Looked inside “Placement and Internship Report 2024-2025” for “B.Tech” / Wrote the answer after 2 round(s) of tool use. / Checked 2 figure(s) against the sources: all found.

### `mess_joining_first_year`
- **Question:** when can first year students join the hostel mess?
- **Mode:** clarify ; **missing:** `report`
- **Answer (trimmed):** Is this for boys or girls?
- **Sources:** 0
- **Trace:** A question about VNIT: looking it up. / Topic: hostel. / Searched VNIT's pages and documents. / Your question fits several different documents (Boys, Girls) with different answers, so I asked which one you mean.

### `conv_hostel_mtech`
- **Question:** What is the hostel fee for first year B.Tech boys for the Winter 2026 session? | what about mtech?
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `40,?080`
- **Answer (trimmed):** **M.Tech at VNIT is a full‑time two‑year (four‑semester) programme offered in several specialisations.**  - The 2024 ISR brochure lists two‑year M.Tech programmes in Applied Mechanics (Structural Engineering, Structural Dynamics & Earthquake Engineering), Architecture & Planning (Urban Planning), Chemical Engineering, 
- **Sources:** 2
- **Trace:** Read the follow-up with the earlier questions as: “What about M.Tech?” / A question about VNIT: looking it up. / Topic: department. / Searched VNIT's pages and documents: 6 passages from 4 sources. / The first search looked relevant (score 3.4). / Wrote the answer from the first search; no further lookups were needed. / Checked 2 figure(s): could not find 2024-2025 in the sources. / Rewrote the answer after the check. Checked 2 figure(s) against the sources: all found.

### `conv_phd_part_time`
- **Question:** What is the tuition fee for full time PhD per semester? | and for part time?
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `15,?000`
- **Answer (trimmed):** **₹25,000 per semester** for a part‑time PhD [​P1].  - The fee sheet lists “Ph.D. (Part‑Time) Per Sem. (in ₹): 25000.00” as the tuition charge per semester [​P1]. - At joining, this amount is paid together with any one‑time fees; thereafter scholars pay a nominal ₹1,000 per year until thesis submission [​P1].  **Note:*
- **Sources:** 4
- **Trace:** Read the follow-up with the earlier questions as: “What is the tuition fee for part time PhD per semester?” / A question about VNIT: looking it up. / Topic: fees. / Searched VNIT's pages and documents: 7 passages from 4 sources. / The first search looked relevant (score 5.6). / Wrote the answer from the first search; no further lookups were needed. / Checked 5 figure(s) against the sources: all found.

### `clarify_profile_mtech`
- **Question:** hostel fee for first year?
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `40,?080`
- **Answer (trimmed):** **Total first‑year hostel fee for M.Tech boys (2026‑27): ₹78,840**  - Room rent (single‑seater): ₹9,000[1] - Maintenance & allied services: ₹11,520[1] - Electricity & water: ₹9,000[1] - Caution money (refundable): ₹1,320[1] - Mess deposit (refundable): ₹48,000[1]  **Calculation:** ₹9,000 + ₹11,520 + ₹9,000 + ₹1,320 + ₹
- **Sources:** 2
- **Trace:** A question about VNIT: looking it up. / Topic: hostel. / Assuming M.Tech boys, from earlier in this chat. / Searched VNIT's pages and documents: 6 passages from 4 sources. / The first search looked relevant (score 8.6). / Wrote the answer from the first search; no further lookups were needed. / Checked 7 figure(s): could not find 78,840 in the sources. / Rewrote the answer after the check. Checked 13 figure(s): could not find 78,840 in the sources. / Part of this answer could not be confirmed, so I've added who to contact.

### `clarify_tuition_vague`
- **Question:** what is the tuition fee?
- **Mode:** agent (openai/gpt-oss-120b) ; **missing:** `clarify with btech`
- **Answer (trimmed):** **Tuition fee (as stated in the VNIT documents)**  - **B.Tech (OPEN/OBC/EWS)** – ₹125 000 per year[1] - **M.Tech** – ₹70 000 per year[2] - **M.Sc** – ₹15 000 per year[3] - **M.Tech / M.Sc (ICCR quota)** – ₹35 000 / ₹7 500 per year respectively[4] - **B.Arch (SC/ST/PwD)** – ₹0 per year[5]  *Note: Figures are taken direc
- **Sources:** 0
- **Trace:** A question about VNIT: looking it up. / Topic: fees. / Searched VNIT's pages and documents: 7 passages from 7 sources. / The first search looked weak (best match scored -0.5, below 0); no better-titled page had a relevant passage, so I continued with what it found. / Wrote the answer from the first search; no further lookups were needed. / Checked 5 figure(s): could not find 125, 70, 15, 35 in the sources. / Rewrote the answer after the check. Checked 5 figure(s): could not find 125, 70, 15, 35 in the sources. / I couldn't find this in VNIT's documents, so I've added who to contact.


## Step 1. Convert the full crawl into data/raw

New: `pipeline/import_site_crawl.py`; `fetch_utils.html_to_text` split out of `fetch_page` (no change in behaviour: three overlapping pages compared, 100%, 100% and 98% word similarity; the 98% page changed on vnit.ac.in between the crawls).

```
$ env -u GENAI_API_KEY $PY import_site_crawl.py
  886  imported
  484  under 40 words
  117  already in data/raw
   74  same text as another page
   26  personal data
   18  skipped section (stores, recruitment)
   14  title: list of people or procurement
    7  mostly Devanagari
    2  listing, archive or attachment page

10 imported titles:
  Dr. (Mrs) S. S. Gadve​ – VNIT Nagpur Applied Mechanics Department
  Dr. R. V. Uddanwadikar – VNIT Nagpur Mechanical Department
  Dr. Abhishek Singh
  Dr. A. S. Dhoble – VNIT Nagpur Mechanical Department
  Deans
  PI Orientation Workshop (Online) – VNIT Nagpur – uba
  Feedback – VNIT Nagpur – Hostel Section
  Dr. Avinash D. Vasudeo_old – VNIT- CIVIL Engineering
  Nagpur – VNIT Nagpur – uba
  Infrastructure – VNIT Nagpur Mechanical Department

10 skipped titles:
  Research links  [under 40 words]
  General Information of Institute  [under 40 words]
  Computing lab | VNIT Nagpur Computer Science Department  [under 40 words]
  Alumni – VNIT Nagpur – Training & Placement Department  [under 40 words]
  Contact Us – VNIT Nagpur Applied Mechanics Department  [under 40 words]
  Faculty – VNIT Nagpur – Hostel Section  [same text as another page]
  Technical Staff – VNIT Nagpur Mathematics Department  [under 40 words]
  Institute Support for Travel  [under 40 words]
  B. Tech – VNIT Nagpur Chemical Engineering Department  [same text as another page]
  Support from Alumni  [under 40 words]
```

- Every one of the 886 `site_*.txt` files has the four header lines (SOURCE_URL, TITLE, FETCHED, CRAWL).
- 15 imported files read by eye: faculty profiles, news posts, hostel pages, department pages. Real content first; no menus or cookie notices. Some sub-sites repeat slider headlines at the top of each page (for example the hostel pages); the 40%-of-pages boilerplate filter was measured (0–7% of words per sub-site, mostly profile headings) and not applied (EXPERIMENTS-LOG §28).
- test_agentic 54/54; chunk_ranks, fact_ranks, evaluate output identical to the baseline (diffed).

**Done when:** import runs cleanly, every file has the header, counts recorded, tests pass, no-key checks unchanged. **Met.**

## Step 2. Rebuild the index and measure: keep it only if better

Commands (from `pipeline/`, no key): `chunk.py && build_index.py && build_facts.py` in the background, logging to `../_trash/rebuild.log` (17-32 minutes per build), then the four no-key checks, diffed per question against Step 0's lists.

| Version | Chunks | test_agentic | chunk_ranks top 7 | top 3 | fact_ranks | evaluate |
|---|---|---|---|---|---|---|
| Baseline (81 pages + documents) | 8,162 | 54/54 | 69/77 | 64/77 | 15/18 | 16/19 |
| First import, as written (886 pages) | 32,261 | (not measured) | | | | |
| Attachment pages left out (868 pages) | 17,922 | 52/54 | 69/77 | 64/77 | 15/18 | 17/19 |
| Plus: sub-site names stripped from titles, near-duplicates left out, corrective step looks at 6 pages (814 pages) | 17,212 | 50/54 | 68/77 | 63/77 | 14/18 | 16/19 |

Where the search misses ranked on the bigger index (attachment pages left out): holiday_holi 8 → 9, phd_tuition_full_time 10 → 10, companies_btech_2425, gs_eligibility, higher_sem_classes_start and msc_tuition not in the top 12 before or after. None moved into the top 7.

What went wrong, in short:
- The first import let through 92 image "attachment" pages (one made 9,555 chunks); fixed in the importer.
- With them gone, nothing new reached the AI, and the search-quality gate lost the T&P page holding the 2025-26 placement figures (2 unit tests failed): dozens of new page titles ending in "Training & Placement Department" outranked it by title.
- Stripping those names from titles, dropping near-duplicate pages and widening the gate's look-up made it worse (68/77, 4 unit tests failing): bare titles such as "Placements" (Chemical) and "About Us" (T&P) then matched institute-wide questions.

**Decision:** not kept (the rule was "more questions reach the AI, at most one baseline hit lost"; no version gained one). The backup index is restored, byte for byte; the checks after restoring are identical to the baseline. The 814 imported pages are kept in `data/raw_site_crawl/` (not read by `chunk.py`), and the importer now writes there. The respond.py change tried in this step was reverted. Details and the reasoning: EXPERIMENTS-LOG §29.

**Done when:** decision and numbers in §29; the index on disk is the kept one (the backup). **Met.** Steps 3-7 run on the original index.

## Step 3. The search misses

Worked on the original index (Step 2 kept it). Two general causes found and fixed; details in EXPERIMENTS-LOG §30.

1. **Table lead-ins repeated on every row** swamped the rows (16% of all document words; the holiday list held two holidays per chunk). `chunk.share_lead_ins` writes a lead-in once per group of rows. Rebuilt: 8,162 → 6,897 chunks.
2. **The same passage ranked twice** (copied onto two pages), wasting the AI's places. `query._drop_repeats` leaves out a passage with over 90% of its words in common with one ranked above it.

Results (`chunk_ranks`, answer passage within the top 7):

| Case (runbook's list, plus msc) | Before | After |
|---|---|---|
| `gs_eligibility` | not in top 12 | **3** |
| `phd_tuition_full_time` | 10 | **7** |
| `msc_tuition` | not in top 12 | **7** |
| `barch_tuition` | 9 | **5** |
| `holiday_holi` | 8 | 9 (not fixed) |
| `companies_btech_2425` | not in top 12 | not in top 12 (not fixed) |
| `higher_sem_classes_start` | not in top 12 | not in top 12 (not fixed) |

Why the three are not fixed: Holi's chunk scores almost top once reranked (4.54 vs 4.66) but other chunks of the same list fill its document's places before reranking; the companies' statistics chunk is 64th before reranking and the reranker prefers the company-name list; the higher-semester start date is in the *Summer* calendar ("Commencement of Next Session: 21st July 2026"), which shares no words with "winter 2026, 2nd year and above". Tried and rejected: grouping "lead: row" lines too (companies → rank 4, but lost a baseline hit; 72/77), and a larger per-source cap (no change).

**Trade:** fact_ranks 15/18 → 14/18, because "end semester exams for first year B.Tech" moved from 3rd to 4th, behind three passages of the first-year exam schedule itself. It still reaches the AI. Recorded in PROGRESS-9 Decisions.

Tests added (no key): `test_table_rows_share_one_lead_in_per_chunk`, `test_long_table_runs_split_but_every_part_keeps_its_lead_in`, `test_repeated_passages_take_one_place_only`. test_agentic 57/57.

**Done when:** each miss fixed or explained (4 fixed, 3 explained, placements reaches the AI through the CRAG gate in the live path); no-key checks no lower than after Step 2 — chunk_ranks higher (73 vs 69), evaluate equal, fact_ranks one lower (recorded trade); §30 written. **Met, with the recorded trade.**

## Step 4. Ask back only when it changes the answer

Changes in `slots.needs_clarification` (EXPERIMENTS-LOG §31):
1. Ask only when the groups' best passages carry **different figures or dates** (`answers_differ`), not merely when documents for two groups were found.
2. A fee question naming no programme asks which programme when the 10 best-titled documents include fee sheets for **3 or more** programmes (`_many_programmes_titled`). The runbook suggested 2; measured, 2 would also ask back on the summer-term and fee-remission questions (recorded in PROGRESS-9 Decisions).
3. Profile in the search: already effective, no change. With M.Tech / boys, "hostel fee for first year?" is searched as "hostel fee for first year? (for M.Tech boys)", the programme filter reads that, and the ₹40,080 sheet ranks 1st with all 7 passages M.Tech hostel sheets. The saved failure was the AI adding the wrong items (₹78,840): an answer problem, re-asked in Step 7.

All 100 cases through `respond.answer`, no key:

| | Ask back | Unexpected or missing |
|---|---|---|
| Before | 1: `clarify_hostel_vague` (B.Tech, B.Arch, M.Sc, Ph.D) | `clarify_tuition_vague` not asked |
| After | 2: `clarify_hostel_vague` (B.Tech, B.Arch, M.Sc, Ph.D); `clarify_tuition_vague` (B.Tech, B.Arch, M.Tech, M.Sc) | none |

`mess_joining_first_year`: answered, not asked (mode not clarify); its best passage is the "Mess Joining Schedule for UG, PG & Ph.D. Students" (rank 1). It had already stopped asking after Step 3's re-chunking; rule 1 makes that a rule, with a test that does not depend on the index.

Tests added: 6 (listed in §31), including the all-100-cases count (skipped without the index). test_agentic 63/63. Retrieval checks identical to Step 3.

**Done when:** tests pass; the clarify cases and `mess_joining_first_year` behave correctly without a key; checks no lower than Step 3; §31 written. **Met.**

## Step 5. The two failing conversations

Diagnosis from the saved traces: `conv_hostel_mtech` failed in the **rewrite** (the LLM returned "What about M.Tech?" unchanged); `conv_phd_part_time` failed in the **answer** (right question, but the total ₹25,000 was given as the tuition).

Fix: `followup._swap_rewrite`, a code-only rewrite before the LLM for follow-ups that only name a slot value (programme, gender, category, year, full-/part-time). New slot `mode_of_study`. Details: EXPERIMENTS-LOG §32.

No key, `respond.answer` with history:
```
conv_hostel_girls | and for girls? -> What is the hostel fee for first year B.Tech girls for the Winter 2026 session? | mode extractive (no GENAI_API_KEY set) | answer passage rank: 3
conv_mtech_tuition | what about M.Tech? -> What is the yearly tuition fee for M.Tech students in the OPEN category? | mode extractive (no GENAI_API_KEY set) | answer passage rank: 1
conv_hostel_mtech | what about mtech? -> What is the hostel fee for first year M.Tech boys for the Winter 2026 session? | mode extractive (no GENAI_API_KEY set) | answer passage rank: 1
conv_phd_part_time | and for part time? -> What is the tuition fee for part time PhD per semester? | mode extractive (no GENAI_API_KEY set) | answer passage rank: 10
conv_placement_cse | and for cse specifically? -> What was the average package for B.Tech in 2024-25 - for cse specifically | mode extractive (no GENAI_API_KEY set) | answer passage rank: 1
conv_holiday | and dussehra? -> When is the Holi holiday in 2026 - dussehra | mode extractive (no GENAI_API_KEY set) | answer passage rank: 1
```

**Done when:** tests pass (66/66, 10 phrasings); the two conversations get the right stand-alone question without a key (both do); checks unchanged; §32 written. **Met.** `conv_phd_part_time`'s passage still ranks 10th (retrieval), recorded for Step 7.

## Step 6. New documents linked from the new pages (count only)

`ingest_documents.discover()` fetches every page live and needs the Drive key for metadata, so a small read-only scan was written instead: `pipeline/count_new_documents.py`. It reads the saved HTML of all 1,628 crawled pages, finds document links by the same rules as `discover()` (Google Drive file ids, vnit.ac.in `.pdf` links), and compares them with `data/documents/inventory.json`. Nothing is downloaded; `inventory.json` and `status.json` were checked unchanged (md5 before and after).

```
$ env -u GENAI_API_KEY $PY count_new_documents.py
Document links in the full crawl: 5098
  already in inventory.json:     529
  new:                           4569 (1939 Google Drive, 2630 vnit.ac.in PDFs)
  new, titled like lists of people or procurement (would be skipped): 44
  new titles about fees, calendar, hostel, scholarship, placement or rules, not already read under another link: 116

The 20 newest of those, by link text:
  Fees Payment Instruction Summer 2027                                              on /section/academics/notice-new/
  Information Brochure Ph.D. Admission (Full-Time/ Part-Time) January 2027          on /section/academics/admission/
  Information Brochure, Rules and Regulations for admission to M.Tech (Research) P  on /section/academics/admission/
  Placement Policy_Batch 2027                                                       on /section/tnp/placement-policy-for-companies/
  Placement Policy_Batch 2027 (Hindi)                                               on /section/tnp/placement-policy-for-companies/
  SOP for Semester Fee Payment Summer 2027                                          on /section/academics/notice-new/
  Extension of last date for Fee Remission 2026-27 application                      on /
  Information Brochure for International Admissions – 2026                          on /study-in-india/
  Kotak Kanya Scholarship 2026-27                                                   on /section/academics/notice-new/
  S-27-Fee Notice Even Term – Academic Year 2026-27 – UG-PG                         on /section/academics/notice-new/
  Shiksha Shakti Scholarship 2026–27 an initiative of the Swami Dayanand Education  on /section/academics/notice-new/
  Academic Calendar Summer Term 2025                                                on /section/rnc/notice/
  Fees Payment Instruction – Summer 2025                                            on /section/rnc/notice-new/
  Fees Payment Instruction – Winter 2025                                            on /section/rnc/notice/
  Information Brochure Admission To Ph.D (Full Time and Part Time) July 2025        on /section/rnc/admission/
  Notice about Documents required for Fee Remission 2025-26                         on /section/rnc/notice/
  Revised W25-Fee Notice Odd Term – Academic Year 2025-26-PhD                       on /section/rnc/notice/
  Revised W25-Fee Notice Odd Term – Academic Year 2025-26-UG-PG                     on /section/rnc/notice/
  SOP for Semester Fee Payment Summer 2025                                          on /section/rnc/notice-new/
  SOP for Semester Fee Payment Winter 2025                                          on /section/rnc/notice/
```

Reading the numbers:
- **4,569 new links** sounds like a lot, but most are old (department archives, 2019-2023 notices) or not useful to students (research papers, newsletters, forms). Filtering by title (fees, calendar, hostel, scholarship, placement, rules), and leaving out the ones whose title the chatbot has already read under another link, leaves **116**.
- The newest of those are worth converting: the **Summer 2027 fee instructions and SOP**, the **S-27 fee notice** for 2026-27, **Ph.D. admission (January 2027)** and **M.Tech (Research)** brochures, the **2026-27 scholarships** (Kotak Kanya, Shiksha Shakti), the **fee remission extension 2026-27**, and the **international admissions brochure 2026**.
- Converting 116 PDFs with Docling takes roughly 2-4 hours and needs the Drive key (`ingest_documents.py`, after running `discover()` so they enter `inventory.json`). The decision is Shivanand's.

**Done when:** counts and list in REPORT9.md. **Met.**

## Step 7. Ask the AI: the 9 failures and a regression sample

Commands (from `pipeline/`), one case at a time, the key read inside the command only:
`GENAI_API_KEY=$(head -1 ~/groq-key.txt | tr -d '

 ') $PY check_answers.py --only <name> --pause 30`

```
=== msc_tuition (08:12)
[PASS] msc_tuition  (tools: 1, check: verified)
Answer check (agent): 1/1 passed
=== holiday_holi (08:13)
[FAIL] holiday_holi missing ['0?4[./-]0?3|\\b4(th)?\\s*Mar|Mar\\w*\\s*4\\b']  (tools: 2, check: verified)
Answer check (agent): 0/1 passed
=== phd_tuition_full_time (08:15)
[PASS] phd_tuition_full_time  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== companies_btech_2425 (08:16)
[FAIL] companies_btech_2425 missing ['\\b121\\b']  (tools: 2, check: verified)
Answer check (agent): 0/1 passed
=== mess_joining_first_year (08:18)
[PASS] mess_joining_first_year  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== conv_hostel_mtech (08:19)
[PASS] conv_hostel_mtech  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== conv_phd_part_time (08:20)
[FAIL] conv_phd_part_time missing ['15,?000']  (tools: 0, check: verified)
Answer check (agent): 0/1 passed
=== clarify_profile_mtech (08:21)
[PASS] clarify_profile_mtech  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== clarify_tuition_vague (08:21)
[PASS] clarify_tuition_vague  (mode: clarify, choices: ['btech', 'barch', 'mtech', 'msc'])
Answer check (agent): 1/1 passed
=== director (08:22)
[PASS] director  (tools: 0, check: verified)
[PASS] unanswerable_director_salary  (tools: 2, check: refused)
[PASS] no_clarify_director  (tools: 0, check: verified)
Answer check (agent): 3/3 passed
=== hostel_fee_first_year (08:25)
[PASS] hostel_fee_first_year  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== btech_fee_open (08:26)
[PASS] btech_fee_open  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== placements (08:27)
[PASS] placements  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== unanswerable_wifi (08:28)
[PASS] unanswerable_wifi  (tools: 2, check: verified)
Answer check (agent): 1/1 passed
=== conv_hostel_girls (08:29)
[PASS] conv_hostel_girls  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== clarify_hostel_vague (08:30)
[PASS] clarify_hostel_vague  (mode: clarify, choices: ['btech', 'barch', 'msc', 'phd'])
Answer check (agent): 1/1 passed
=== clarify_then_answer (08:31)
[PASS] clarify_then_answer  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== classes_start_fy (08:32)
[PASS] classes_start_fy  (tools: 0, check: verified)
Answer check (agent): 1/1 passed
=== finished 08:33
```

Failures still failing, first 300 characters of the answer:
- **holiday_holi:** "Yes – Holi is observed as a restricted holiday on 03 March 2026 at VNIT. The “List of Holiday’s during the year 2026” records Holika Dahan – Date: 03.03.2026 …" Wrong: the gazetted list has "Holi — 04.03.2026". That row ranks 9th, so the AI never saw it.
- **companies_btech_2425:** "I’m sorry, but none of the provided documents state the total number of companies that visited for B.Tech placements in 2024-25 …" The agent searched and looked inside the 2024-25 report for "total companies", but the row "Number of Companies Visited — B.Tech: 121" did not come up.
- **conv_phd_part_time:** "₹25,000 per semester for a part-time PhD …" The rewrite is right now ("What is the tuition fee for part time PhD per semester?"), but ₹25,000 is the per-semester total; the tuition row (₹15,000) ranks 10th.

Mode, tools, verifier: all 17 written answers "agent (openai/gpt-oss-120b)", 0-2 tool calls, verifier "verified" (or "refused" for the must-decline case); the 2 clarify cases asked with the expected choices.

Tokens: about 99,000 for 20 cases (gpt-oss-120b), under the 120,000 budget; no daily-limit stop. Regression: 11/11 pass; nothing reverted; no pattern changed, no `--rescore`.

**New overall: 97/100 saved results pass** (was 91/100). Before/after table: EXPERIMENTS-LOG §33.

**Done when:** every case asked; new count computed; §33 written. **Met.**

## Step 8. Docs and the morning report

- `README.md`: project status (20 Nov), web pages and the kept-aside full crawl, chunks 6,897, table rows 23,088, answer quality 97/100, tests 66/66, measured-quality table (chunk_ranks 73/77, fact_ranks 14/18), known limitations (rows of long tables; the full crawl not searched), what to do next.
- `APPLICATION.md`: status table (same numbers), retrieval (repeated passages dropped), clarify-or-assume rule.
- `HOW-TO-RUN.md`: test count and time, `check_answers.py --only`, `chunk_ranks.py` in the quality checks, `data/raw_site_crawl/`.
- EXPERIMENTS-LOG §26: note that the search changed on 20 Nov and the ablation table must be re-run.
- **Website check** (no key, port 8010, server started with `uvicorn api.main:app --port 8010`, the same command `start_website.bat` runs on 8000; stopped afterwards): `/health` ok; `/site/` 200 ("Home | VNIT Nagpur (student project demo)"); `/site/engineering/cse/faculty/` 200; `/ask` "What is the hostel fee?" → clarify (B.Tech, B.Arch, M.Sc, Ph.D); `/ask` "Who is the Director of VNIT?" → extractive answer naming Prof. (Dr.) Prem Lal Patel. The website in `../vnit-website` was not rebuilt or changed.

**Done when:** docs updated, every step marked, last commit in. **Met.**
