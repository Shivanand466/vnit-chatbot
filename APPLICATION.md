# APPLICATION.md — VNIT Website Chatbot: technical reference

What this application is, how it works, what's verified (with measured numbers), and the reasons behind its design. For **starting and demoing** it, see `HOW-TO-RUN.md`. For the evidence behind each design choice, see `EXPERIMENTS-LOG.md`.

---

## 1. What it is

A chatbot that answers students' questions about VNIT Nagpur using **only** the institute's own website and documents, with a source link for every answer. It covers admissions, fees, hostels, scholarships, notices, academic calendars, placements, departments and administration.

**Constraints that shaped every decision:**
- **Zero budget.** Free and open-source only. The LLM is Groq's free API; retrieval runs locally.
- **Honesty over coverage.** When the answer isn't in its sources, it must say so, never guess.

**In one sentence:** crawl the website and its linked documents into plain text → split into ~150-word chunks → index them two ways (meaning and keywords) → for each question, find candidate chunks with hybrid search, re-order them with a reranker, and have an LLM write a cited answer from only those chunks → serve it through a small web API and chat page.

---

## 2. Status (as of 2026-10-03)

| Part | Status |
|---|---|
| Web pages | **81** pages crawled from vnit.ac.in |
| Documents (PDF notices, fee sheets, calendars…) | **406 converted** (`data/raw/doc_*.txt`). 599 found, 456 selected; of those, 33 excluded as lists of people, 5 no readable text, 3 Hindi-only, 7 failed (3 are dead links on vnit.ac.in). Re-run `ingest_documents.py convert`; it skips finished ones |
| Chunks in the index | **8,147** |
| Retrieval | Title-prefixed chunks → hybrid (sentence embeddings + TF-IDF keywords) → programme/year contradiction filter → 60-candidate cross-encoder reranking → up to 5 passages per (sub-)question |
| Page-level benchmark (`evaluate.py`, 19 questions) | 16/19 |
| Answer-chunk ranks (`fact_ranks.py`) | **15/18** |
| Real-path retrieval (`chunk_ranks.py`, 32 questions through `agent.answer`) | **29/32** have the answer-bearing passage among the 7 sent to the LLM; 26/32 in the top 3 |
| End-to-end answer check (`check_answers.py`, 39 cases) | **31/39** on the last complete run; the retrieval changes made after it are measured only by `chunk_ranks.py` so far, because Groq's free daily token quota ran out — re-run to confirm (see §6) |
| LLM | Groq `openai/gpt-oss-20b` (free tier) |
| API + chat page | Working; one-click start via `start_chatbot.bat`, verified live on 2026-10-03. Follow-up questions ("and for girls?") and a thumbs up/down rating on every answer |
| Deployment | Docker image builds locally; public link from the laptop via `start_public_link.bat` (Cloudflare quick tunnel). Hugging Face Spaces now requires a paid PRO account for Docker Spaces, so `deploy/deploy_to_hf.py` is ready but unused |

---

## 3. Directory structure

```
vnit-chatbot/
├── start_chatbot.bat          <- double-click to run
├── HOW-TO-RUN.md              <- plain-language guide
├── APPLICATION.md             <- this file
├── EXPERIMENTS-LOG.md         <- what was tried, measured, adopted or rejected
├── README.md                  <- project overview
├── requirements.txt           <- main app (Anaconda environment)
├── requirements-pdf.txt       <- document reader (separate environment, Docling)
├── api/main.py                <- FastAPI: GET /health, POST /ask, POST /feedback
├── frontend/index.html        <- chat page
├── data/
│   ├── raw/*.txt              <- web pages; doc_*.txt are converted documents
│   ├── documents/
│   │   ├── inventory.json     <- every document link found, with title/date/type
│   │   └── status.json        <- per document: ingested / skipped (and why) / error
│   └── processed/
│       ├── chunks.jsonl
│       ├── index.pkl
│       └── answer_check.json  <- last end-to-end answer check results
└── pipeline/
    ├── fetch_utils.py         <- polite HTTP fetch, robots.txt check, link extraction
    ├── crawl.py / recrawl.py  <- discover new pages / refresh known pages
    ├── drive_utils.py         <- Google Drive API downloads (key from a file, never printed)
    ├── doc_convert.py         <- PDF → text with Docling (layout, tables, OCR)
    ├── ingest_documents.py    <- discover, select, download, convert documents (crash-safe)
    ├── chunk.py               <- text → ~150-word chunks
    ├── build_index.py         <- embeddings + TF-IDF index; pre-downloads the reranker
    ├── followup.py            <- rewrites "and for girls?" to stand on its own
    ├── programme_terms.py     <- which programme/year/gender a text is about
    ├── query.py               <- hybrid search + contradiction filter + reranking
    ├── agent.py               <- splits compound questions, retrieves per part and whole
    ├── generate.py            <- builds the prompt, calls the LLM, extractive fallback
    ├── feedback_summary.py    <- counts the thumbs up/down ratings
    ├── evaluate.py            <- page-level benchmark
    ├── fact_ranks.py          <- answer-chunk rank check (no LLM needed)
    ├── chunk_ranks.py         <- same, but through agent.answer, the real path
    └── check_answers.py       <- end-to-end answer check (uses the LLM)
```

Outside the project folder (deliberately, so they never sync or get shared):
- `C:\Users\shiva\groq-key.txt`: Groq key, read by `start_chatbot.bat`
- `C:\Users\shiva\vnit-secrets.txt`: Google Drive API key, read by `drive_utils.py`
- `C:\Users\shiva\.venvs\vnit-pdf\`: document-reader environment (~1.4 GB)
- `C:\Users\shiva\.cache\vnit-chatbot\pdfs\`: downloaded PDFs (re-used on re-runs)
- `C:\Users\shiva\vnit-chatbot-backups\`: backups taken before major changes

---

## 4. Where the knowledge comes from

**Web pages** (`crawl.py`): breadth-first crawl from the homepage, one request per second, respecting robots.txt. Navigation, headers, footers and scripts are stripped.

**Documents** (`ingest_documents.py`): most VNIT notices, fee sheets and calendars are **PDFs on Google Drive**, linked from the website (e.g. 159 on the academic notices page), not PDFs on vnit.ac.in.
1. `discover` scans every crawled page for Drive and PDF links and records each document's title (the link text), date and type via the Drive API. Google's robots.txt forbids automated downloads through normal Drive links; the **official Drive API** with an API key is Google's supported route for programs.
2. `select()` drops documents that shouldn't be in a chatbot:
   - **lists of people** (seating plans, merit/selection lists, allotments, results, class-committee lists), which are personal data;
   - tenders and procurement notices;
   - blank forms;
   - Hindi-only documents (the models are English-only).
   It sorts the rest into priority tiers: **0** fees, scholarships, hostel, calendars, admission instructions, placements, rule book; **1** other 2026 academic and admission notices; **2** everything else.
3. `convert` downloads each document and converts it with Docling (first 25 pages), then applies a **content check**: anything containing student roll numbers or student email addresses is discarded even if its title looked harmless. It writes `data/raw/doc_<id>.txt` with the document's date.
4. A **supervisor** runs conversion in a worker process. Docling's native code can crash (a real segmentation fault happened) or hang; the supervisor marks that one document as failed and carries on with the rest.

**How tables are handled** (`doc_convert.py`): each table row becomes a self-contained line carrying its column headings *and* the sentence that introduced the table, e.g.
`...students admitted in SC/ ST/ PwD Category in B. Tech. | Fees per year: Tuition Fee — First Year: 0; Second Year: 0; ...`
This matters twice over:
- Plain PDF text extraction garbled a programme table and produced a wrong answer (EXPERIMENTS-LOG §5).
- One fee PDF has identical-looking tables for different student categories, told apart only by the sentence above each table.

---

## 5. How a question is answered

0. **Resolve a follow-up** (`followup.resolve`): retrieval has no memory, so "and for girls?" matches nothing on its own. When a question cannot stand alone — it opens with a connective ("and…", "what about…") or carries a referring word with no subject of its own — it is rewritten against the last three questions, and the chat page shows the result as "Understood as: …". The rewrite is one short LLM call (`reasoning_effort: "low"`, measured at ~117 completion tokens); if there is no key or the call fails, the previous question and the follow-up are glued together, which reads awkwardly but still retrieves. An ordinary question is never touched and costs nothing extra.
1. **Split** (`agent.decompose`): "X and Y" becomes two sub-questions when both parts are real questions. A pronoun in the second part is replaced by the first part's subject ("...and when was **it** announced" → "when was **the 5G lab** announced").
2. **Retrieve** (`query.retrieve`) for each sub-question, and also for the whole question (splitting can lose shared context):
   1. **Hybrid search:** rank all chunks by meaning (sentence embeddings, `all-MiniLM-L6-v2`) and by keywords (TF-IDF), then fuse the two rankings (keyword weight 0.5, K=30).
   2. **Set aside contradictions** (`programme_terms.py`): a candidate that states a different degree programme (B.Tech vs M.Tech, with UG/PG standing for their members), a different academic year (2025-26 style) or a different gender of student than the question asks about is skipped, scanning further down the fused ranking to keep the pool full. A candidate stating none of them stays eligible, since many answers come from pages that never spell one out. This is what tells the 19 near-identical hostel fee sheets apart — all three axes were needed: without the gender axis, "the hostel fee for first year B.Tech girls" was answered from the boys' and M.Tech sheets even though the girls' sheet was the 3rd-ranked candidate going into the reranker.
   3. **Rerank:** a cross-encoder (`ms-marco-MiniLM-L-6-v2`) reads the top **60** candidates side by side with the question and re-orders them. No single source may fill more than 6 of those 60, so a long list-shaped document (a placement report's company list) cannot crowd out everything else.
3. **Compose** (`generate.llm_answer`): the whole-question chunks go in first (up to 3), then up to 5 per sub-question. Limits are 1,000 characters per chunk and 6,000 in total, to stay within Groq's free-tier rate limit. Document chunks are labelled with their date. The LLM is told to:
   - use only these passages and cite them;
   - say plainly when they don't cover something;
   - state which student group a figure applies to;
   - prefer the newest document when documents disagree.
4. **Fallback:** if there's no key or the LLM call fails, the answer is built from the top passages directly, and `mode` says `extractive (reason)`. The API always reports `mode`, and the chat page shows it. An *empty* answer counts as a failure too: gpt-oss-20b can spend its whole token budget on its reasoning channel and return no content, which was briefly shown to a user as a blank answer, so `generate.py` retries once with `reasoning_effort: "low"` and then falls back to extractive.
5. **Rating** (`POST /feedback`): each answer carries thumbs up/down. A rating appends one JSON line to `data/feedback/feedback.jsonl` — timestamp, rating, question, answer, mode — with no IP address, since counting useful answers does not require knowing who asked. The file is gitignored: it holds real students' questions, which are their data, not the project's source. It has its own rate-limit bucket so rating answers cannot consume someone's allowance of questions.

---

## 6. Measured quality

Run on 2026-10-03 with 81 pages + 406 documents (8,147 chunks). Full answers: `data/processed/answer_check.json`.

> **Status of these numbers.** The 18-question answer check scored **17/18**. It was then widened to **39 cases** (34 facts, 5 that must be declined, 2 two-turn conversations), which immediately found four real bugs — see EXPERIMENTS-LOG.md §18. The widened suite's last complete run was **31/39**; the retrieval changes made after it (pooling both phrasings, per-source cap 4, 7 passages per sub-question) are so far measured only by `chunk_ranks.py`, because the day's free Groq quota ran out. **Re-run `check_answers.py` once the quota resets** to get a final end-to-end figure. The honest reading today: retrieval is measurably better than when 17/18 was recorded, on a test set twice the size, and the end-to-end number needs confirming.

| Check | 148 documents (2026-09-22) | 406 documents (2026-10-03) |
|---|---|---|
| `check_answers.py` end-to-end | 13/18 | **17/18** |
| `fact_ranks.py` answer chunk in top 3 | 12/18 | 14/18 (11 at rank 1) |
| `evaluate.py` page-level | 16/19 | **17/19** |
| Unanswerable questions declined | 2/2 | 2/2 |

- **Correct (17):** Civil UG intake, 5G announcement date, Chemical and Electrical M.Tech specialisations, Director, Registrar, Dean (Academic) email, Mechanical founding year, B.Tech OPEN tuition (₹1,25,000/yr) and SC/ST tuition (nil), Kotak Kanya amount, IDFC deadline, first-year boys' hostel fee for Winter 2026 (₹32,150), Winter 2026 class start (19 Aug 2026), end-semester exams (7–15 Dec 2026), plus both unanswerable questions correctly declined.
- **The single failure:** 2025-26 placement figures (678 students, 170 companies). Stated in one paragraph of the T&P page, which fuses to rank 293 because two placement reports contribute hundreds of company-list chunks matching the same words. Diagnosed stage by stage in EXPERIMENTS-LOG.md §16; left failing because the chatbot declines rather than quoting the 2024-25 numbers.

What moved the numbers this round (all measured, see EXPERIMENTS-LOG.md §10–16):
- **Reranking pool 30 → 60** (§12): facts 13 → 15/18 on the same data. The pool had been tuned when the corpus was a quarter of its final size, which had quietly become the main limit on accuracy. A pool of 100 measured no better.
- **Programme/year contradiction filter** (§13): facts 14 → 15/18; the hostel-fee question >20 → rank 1.
- **Calendar table fixes** (§“Fix calendar table text” commit): exam-slot rows now labelled, month-day grids dropped, letterhead mojibake removed — the end-semester answer went from wrong to correct.
- **Two text bugs** (§15): page encoding sniffing (UTF-8 punctuation was stored as mojibake) and rejoining sentences split by inline markup.
- **Rejected after measuring:** programme tags appended to the keyword index (§10, worse), and capping sources in the *final* results (§14, broke a question needing several chunks of one document).

Earlier rounds: adding titles to chunks 11 → 12/18; sending 5 passages instead of 3 fixed a confident wrong answer ("classes start 4 Jan 2027", read from "Commencement of Next Session"). Answers vary a little between runs — one question passed in one run and failed in the next two with no data change.

---

## 7. Key design decisions (details and numbers in EXPERIMENTS-LOG.md)

- **Embeddings over TF-IDF as the base**, despite a lower page-level score at the time: they found the specific answer-bearing chunk that TF-IDF buried.
- **Hybrid + reranker:**
  - Keyword search rescues exact-term questions ("Registrar").
  - The reranker stops hundreds of documents from crowding out web-page answers.
  - Both were adopted only after measurement showed they beat the alternatives.
- **Re-tune the pool when the corpus grows:** the 30-candidate pool was right for 122 sources and quietly wrong for 487. Raising it to 60 was the largest single accuracy gain of the project (§12 in EXPERIMENTS-LOG.md). Any corpus change should be followed by re-running the three checks.
- **Filter candidates, don't re-weight text:** adding programme tags to the indexed text diluted TF-IDF and measured worse; deciding which candidates compete, and leaving scoring alone, worked (§10 vs §13).
- **Docling for PDFs, not plain extraction:** plain extraction caused a wrong answer.
- **Rows as sentences with their lead-in context:** prevents mixing up fee categories and losing column meaning when chunked.
- **Chunk size 150 words:** best of 60/80/100/150 in testing.
- **Personal data excluded by title *and* content:** titles alone missed a list with students' phone numbers.
- **The model never pressured to answer:** in every test round it declined rather than invent. Don't change the prompt in a way that pushes it to always answer.
- **Keys live outside the project, are never printed, and are scrubbed from error messages:** Google's key would otherwise appear in request error text.

---

## 8. Known limitations

- **A single paragraph can lose to a long list.** The failure in §6: hundreds of similar chunks from one document outweigh one page's paragraph in both rankings. Pool diversification helps but cannot reach fused rank 293.
- **Designed posters** can pair a label with the wrong value (the IDFC poster's "Application deadline" landed beside the award amount). The LLM declines rather than guessing.
- Old documents are included (dated, the LLM is told to prefer the newest, and contradicting years are filtered), so questions about past terms may still get older answers.
- Personal-data filtering is heuristic (titles + roll-number/student-email density): 33 documents excluded, and all 406 converted documents re-checked against it on 2026-10-03, but it's not a guarantee.
- 15 selected documents yielded no usable text (7 errors including 3 dead links on vnit.ac.in, 5 empty, 3 Hindi-only); scanned PDFs occasionally contain OCR slips like "Nag pur".
- The rate limiter's memory is per server process and resets on restart; fine for a demo, not for heavy public use.
- A conversion run killed between writing a document's text file and saving `status.json` leaves a text file with no status entry (14 such files exist). They are complete, filtered documents — the personal-data check runs before the write — but a later run will convert them again.

---

## 9. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GENAI_API_KEY` | none (`start_chatbot.bat` reads `groq-key.txt`) | Groq key; without it answers are extractive |
| `GENAI_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible provider |
| `GENAI_MODEL` | `openai/gpt-oss-20b` | If Groq retires it (404 `model_not_found`), pick a current one from `GET {base_url}/models` |
| `VNIT_KEY_FILE` | `%USERPROFILE%\vnit-secrets.txt` | Google Drive API key file |
