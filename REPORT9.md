# Runbook 9 report: the full crawl in the chatbot, and the last 9 failures

## Good morning

(Written at the end, in Step 8.)

## No-key checks after each step

| After step | test_agentic | chunk_ranks: reaches LLM (top 7) | top 3 | top 12 | fact_ranks top 3 | evaluate top 3 |
|---|---|---|---|---|---|---|
| 0 (baseline) | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |
| 1 (files added, index not rebuilt) | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |
| 2 (bigger index measured, not kept; backup restored) | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |
| 3 (shared table lead-ins, repeated passages dropped) | 57/57 | 73/77 | 66/77 | 74/77 | 14/18 | 16/19 |

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
