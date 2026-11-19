# Runbook 9 report: the full crawl in the chatbot, and the last 9 failures

## Good morning

(Written at the end, in Step 8.)

## No-key checks after each step

| After step | test_agentic | chunk_ranks: reaches LLM (top 7) | top 3 | top 12 | fact_ranks top 3 | evaluate top 3 |
|---|---|---|---|---|---|---|
| 0 (baseline) | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |

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

