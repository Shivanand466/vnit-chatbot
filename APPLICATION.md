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

## 2. Status (as of 2026-09-22)

| Part | Status |
|---|---|
| Web pages | **81** pages crawled from vnit.ac.in |
| Documents (PDF notices, fee sheets, calendars…) | **148 converted** (`data/raw/doc_*.txt`). 599 found, 456 selected; ~305 still to convert (40 in tier 0, all of tiers 1–2). Resume with `ingest_documents.py convert --tiers N`; it skips finished ones |
| Chunks in the index | **2,678** (81 web pages + 148 documents) |
| Retrieval | Title-prefixed chunks → hybrid (sentence embeddings + TF-IDF keywords) → cross-encoder reranking → up to 5 passages per (sub-)question |
| Page-level benchmark (`evaluate.py`, 19 questions) | **16/19 (84%)**; the misses are now mostly documents out-ranking the expected web page |
| Answer-chunk ranks (`fact_ranks.py`) | **12/18** facts have the answer-bearing chunk in the top 3 |
| End-to-end answer check (`check_answers.py`) | **13/18 correct**, 2/2 unanswerable questions correctly refused; failures: 4 honest "not found", 1 partly wrong (see §6) |
| LLM | Groq `openai/gpt-oss-20b` (free tier) |
| API + chat page | Working; one-click start via `start_chatbot.bat` |
| Deployment | Docker image builds locally; Hugging Face Spaces deploy script ready (`deploy/deploy_to_hf.py`), not yet live |

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
├── api/main.py                <- FastAPI: GET /health, POST /ask
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
    ├── query.py               <- hybrid search + reranking: retrieve(question, k)
    ├── agent.py               <- splits compound questions, retrieves per part and whole
    ├── generate.py            <- builds the prompt, calls the LLM, extractive fallback
    ├── evaluate.py            <- page-level benchmark
    ├── fact_ranks.py          <- answer-chunk rank check (no LLM needed)
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

1. **Split** (`agent.decompose`): "X and Y" becomes two sub-questions when both parts are real questions. A pronoun in the second part is replaced by the first part's subject ("...and when was **it** announced" → "when was **the 5G lab** announced").
2. **Retrieve** (`query.retrieve`) for each sub-question, and also for the whole question (splitting can lose shared context):
   1. **Hybrid search:** rank all chunks by meaning (sentence embeddings, `all-MiniLM-L6-v2`) and by keywords (TF-IDF), then fuse the two rankings (keyword weight 0.5, K=30).
   2. **Rerank:** a cross-encoder (`ms-marco-MiniLM-L-6-v2`) reads the top 30 candidates side by side with the question and re-orders them.
3. **Compose** (`generate.llm_answer`): the whole-question chunks go in first (up to 3), then up to 5 per sub-question. Limits are 1,000 characters per chunk and 6,000 in total, to stay within Groq's free-tier rate limit. Document chunks are labelled with their date. The LLM is told to:
   - use only these passages and cite them;
   - say plainly when they don't cover something;
   - state which student group a figure applies to;
   - prefer the newest document when documents disagree.
4. **Fallback:** if there's no key or the LLM call fails, the answer is built from the top passages directly, and `mode` says `extractive (reason)`. The API always reports `mode`, and the chat page shows it.

---

## 6. Measured quality

Run on 2026-09-22 with 81 pages + 148 documents (2,678 chunks). Full answers: `data/processed/answer_check.json`.

- **Correct (13):** Civil UG intake, 5G announcement date, Chemical specialisations, Electrical M.Tech specialisations, Director, Dean (Academic) email, Mechanical department founding year, Registrar, SC/ST tuition (nil), Kotak Kanya amount, first-year Winter 2026 start date, plus both unanswerable questions correctly declined.
- **Honest "not in my sources" (4):**
  - B.Tech OPEN tuition: fee-estimate PDF not converted yet.
  - 2025-26 placement numbers: the T&P page is out-ranked by placement-report PDFs.
  - First-year hostel fee: 19 near-identical hostel fee sheets; "B.Tech" vs "M.Tech" confusion.
  - IDFC deadline: the poster's layout separates the date from its label.
- **Partly wrong (1):** end-semester exam dates. The calendar's exam-slot rows (A–H) came out without the word "slot", so the LLM read them as conflicting versions and said 7–14 Dec instead of 7–15 Dec.

Changes measured on the way (see EXPERIMENTS-LOG.md):
- Adding titles to chunks: 11 → 12/18 facts found.
- Sending 5 passages instead of 3 fixed a confident wrong answer ("classes start 4 Jan 2027", read from "Commencement of Next Session") at the cost of one previously-passing answer turning into an honest "not found". Answers also vary a little between runs.

---

## 7. Key design decisions (details and numbers in EXPERIMENTS-LOG.md)

- **Embeddings over TF-IDF as the base**, despite a lower page-level score at the time: they found the specific answer-bearing chunk that TF-IDF buried.
- **Hybrid + reranker:**
  - Keyword search rescues exact-term questions ("Registrar").
  - The reranker stops hundreds of documents from crowding out web-page answers.
  - Both were adopted only after measurement showed they beat the alternatives.
- **Docling for PDFs, not plain extraction:** plain extraction caused a wrong answer.
- **Rows as sentences with their lead-in context:** prevents mixing up fee categories and losing column meaning when chunked.
- **Chunk size 150 words:** best of 60/80/100/150 in testing.
- **Personal data excluded by title *and* content:** titles alone missed a list with students' phone numbers.
- **The model never pressured to answer:** in every test round it declined rather than invent. Don't change the prompt in a way that pushes it to always answer.
- **Keys live outside the project, are never printed, and are scrubbed from error messages:** Google's key would otherwise appear in request error text.

---

## 8. Known limitations

- ~305 selected documents not yet converted; their contents can't be answered.
- Near-identical documents (hostel fee sheets per year/gender, many calendars) and B.Tech/M.Tech wording are the main retrieval weakness.
- Grid-shaped tables (calendar day grids, exam slots) and designed posters convert into confusing text.
- Old documents are included (dated, and the LLM is told to prefer the newest), so questions about past terms may get older answers.
- Personal-data filtering is heuristic (titles + roll-number/student-email density). It caught every list seen in testing, but it's not a guarantee.
- The rate limiter's memory is per server process and resets on restart; fine for a demo, not for heavy public use.

---

## 9. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GENAI_API_KEY` | none (`start_chatbot.bat` reads `groq-key.txt`) | Groq key; without it answers are extractive |
| `GENAI_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible provider |
| `GENAI_MODEL` | `openai/gpt-oss-20b` | If Groq retires it (404 `model_not_found`), pick a current one from `GET {base_url}/models` |
| `VNIT_KEY_FILE` | `%USERPROFILE%\vnit-secrets.txt` | Google Drive API key file |
