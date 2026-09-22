# VNIT Chatbot

A chatbot that answers students' questions about **VNIT Nagpur** (admissions, fees, hostels, scholarships, notices, academic calendars, placements, departments, administration) using **only** the institute's own website and documents, and shows the source of every answer.

Final-year project (FYP). Built with free and open-source tools only.

> **How to start it and demo it:** see [`HOW-TO-RUN.md`](HOW-TO-RUN.md), written in plain language.
> **How it works in detail:** see [`APPLICATION.md`](APPLICATION.md).
> **What was tried and measured along the way:** see [`EXPERIMENTS-LOG.md`](EXPERIMENTS-LOG.md).

---

## What it does

- A student types a question in a chat page, for example *"What is the B.Tech tuition fee?"* or *"When do first-year classes start in Winter 2026?"*
- The chatbot searches VNIT's web pages and documents, picks the most relevant passages, and an AI model (Groq, free tier) writes a short answer **using only those passages**, with links to them.
- If the answer isn't in VNIT's material, it **says so instead of making something up**. In every test round so far, it has never invented an answer.

## How it works (short version)

```
 vnit.ac.in pages ─┐                                   ┌─ hybrid search (meaning + keywords)
                   ├─► plain text ─► ~150-word chunks ─┤─ reranker picks the best passages
 Google Drive PDFs ┘   (Docling: tables, scans)        └─ AI writes a cited answer ─► chat page
 (notices, fee sheets, calendars)
```

- **Web pages:** a polite crawler (1 request per second, respects robots.txt).
- **Documents:** most VNIT notices are PDFs on Google Drive. They're downloaded through the official Google Drive API and read with **Docling**, which understands page layout, keeps tables as proper rows and reads scanned pages (OCR).
- **Privacy:** lists of people (seating plans, merit lists, class-committee lists with phone numbers) are **excluded**, both by title and by checking the content for student roll numbers.
- **Search:** sentence embeddings (`all-MiniLM-L6-v2`) + keyword search (TF-IDF), combined, then re-ordered by a cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`).
- **Answering:** Groq `openai/gpt-oss-20b`. If the AI can't be reached, the chatbot falls back to showing the best passages, and it always says which mode was used.

---

## Project status (22 September 2026)

| Part | Status |
|---|---|
| Web pages | ✅ 81 pages from vnit.ac.in |
| Documents | 🟡 **148 converted** (fee sheets, 19 hostel fee sheets, academic calendars, scholarships, fee notices, admission instructions, Academic Rule Book, placement brochure…). 599 document links found; 456 selected after filters; **~305 still to convert** (40 top-priority, then 265 general notices) |
| Search index | ✅ 2,678 chunks (web pages + the 148 documents) |
| Answer quality | 🟡 13 of 18 test questions answered correctly end to end; both "impossible" questions correctly refused (details below) |
| Chat page | ✅ Works; one-click start with `start_chatbot.bat` (Windows) |
| Safety | ✅ Keys kept outside the project and never printed; per-visitor rate limit; answers can't inject code into the page |
| Deployment | 🟡 **Public link from the laptop** with `start_public_link.bat` (free Cloudflare tunnel). Not always-online: Hugging Face now charges (PRO) for Docker Spaces, and free hosts with 512 MB of memory are too small (see "Deploying" below) |

### Measured quality

Three automatic checks, run on 22 Sept 2026 with the 148 documents included:

| Check | What it measures | Result |
|---|---|---|
| `check_answers.py` | Asks the real chatbot 18 questions and checks each answer against facts verified by hand in the source pages | **13/18 correct** |
| (same) | Two questions whose answers are *not* in VNIT's material | **2/2 correctly refused** (no made-up answers) |
| `fact_ranks.py` | Is the passage containing the answer among the top 3 found? | 12/18 |
| `evaluate.py` | Is the right *page* among the top 3? (19 questions) | 16/19 (84%) |

Correct answers include:
- Civil Engineering intake (120/year);
- the 5G lab announcement date (27 Oct 2023);
- Electrical M.Tech specialisations;
- the Director, the Registrar, and the Dean (Academic)'s email;
- when the Mechanical department started (1960);
- SC/ST tuition (nil);
- the Kotak Kanya scholarship amount (₹1.5 lakh/year);
- when first-year classes start in Winter 2026 (19 Aug 2026).

The 5 that failed:
- **4 honest "not in my sources" answers:**
  - B.Tech OPEN-category fee: its document isn't converted yet.
  - Placement numbers 2025-26: out-ranked by the new placement-report documents.
  - First-year hostel fee: many near-identical hostel fee sheets.
  - IDFC scholarship deadline: the poster's layout puts the date on a separate line.
- **1 partly wrong:** end-semester exam dates. The calendar lists exam *slots* A–H, and the AI took them for conflicting versions, giving 7–14 Dec instead of 7–15 Dec.

Full answers are saved in `data/processed/answer_check.json`.

### Known limitations

- **~305 documents not converted yet** (see "What to do next"). Questions about notices in that group can't be answered yet.
- **Very similar documents** (e.g. 19 hostel fee sheets for different years and genders, many academic calendars) sometimes get the wrong one picked. "B.Tech" vs "M.Tech" is a known weak spot.
- **Calendar grids and posters:** tables laid out as grids (exam slots A–H, month-day grids) or designed posters can come out confusing, and the AI may misread them.
- **Answers can vary slightly between runs**, because the AI model isn't perfectly repeatable.
- **Old documents** (e.g. 2024 calendars) are included. The AI is told to prefer the newest and each document's date is shown, but a question about an old term could still get a stale answer.
- A few documents couldn't be read: 1 crashed the PDF reader, 1 had no text, and scanned PDFs sometimes contain small OCR slips like "Nag pur".
- It only knows what was downloaded. Refreshing the data is manual (see `HOW-TO-RUN.md` §5).

---

## What to do next

In order of value:

1. **Finish converting documents** (about 3–4 hours, runs by itself; keep the laptop plugged in so it doesn't sleep):
   ```
   cd pipeline
   %USERPROFILE%\.venvs\vnit-pdf\Scripts\python.exe ingest_documents.py convert --tiers 0
   %USERPROFILE%\.venvs\vnit-pdf\Scripts\python.exe ingest_documents.py convert --tiers 1
   %USERPROFILE%\.venvs\vnit-pdf\Scripts\python.exe ingest_documents.py convert --tiers 2
   ```
   It skips finished documents and survives crashes, so it can be stopped and restarted at any time.
2. **Rebuild the index and re-check quality**:
   ```
   python chunk.py
   python build_index.py
   python evaluate.py
   python fact_ranks.py
   python check_answers.py        (needs GENAI_API_KEY set)
   ```
3. **Fix the "similar documents" weak spot**, e.g. by treating "B.Tech", "Bachelor of Technology" and "UG" as the same when searching. Keep the fix only if the three checks above get better, not worse.
4. **Improve calendar tables:** label exam-slot rows (A–H) as slots and drop the month-day grid rows, then re-check the end-semester question.
5. **Always-online hosting** (optional): replace PyTorch with the lighter ONNX runtime so the app fits a free 512 MB host such as Render, then re-run the three checks. Or pay for Hugging Face PRO and run `deploy/deploy_to_hf.py` unchanged.
6. **For the FYP report:** the numbers in "Measured quality", `EXPERIMENTS-LOG.md` (what was tried and why) and `docs/development-history/` (every test round's report) are ready-made evidence.

---

## Running it locally

On Windows: double-click **`start_chatbot.bat`**. The chat page opens at `http://127.0.0.1:8000/` when it's ready. It needs:
- Anaconda Python with `pip install -r requirements.txt`;
- a Groq key saved alone on one line in `C:\Users\<you>\groq-key.txt`.

Full steps, demo questions and troubleshooting are in [`HOW-TO-RUN.md`](HOW-TO-RUN.md).

## Deploying

**GitHub stores the code, but it can't run the chatbot:** the chatbot needs a Python server running all the time.

**Free public link from your laptop (current method):** double-click **`start_public_link.bat`**. It starts the chatbot and prints a temporary `https://….trycloudflare.com` address that anyone can open, for example on a phone. It works only while the laptop is on and both windows are open, and the address changes each time.

**Hugging Face Spaces (needs a paid PRO account since 2026):** trying it on 22 Sept 2026 returned *"hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription"*. With PRO:

1. Create an account at https://huggingface.co/join.
2. Go to https://huggingface.co/settings/tokens → **Create new token** → type **Write** → copy it.
3. Save the token alone on one line in `C:\Users\<you>\hf-token.txt`.
4. Run:
   ```
   pip install huggingface_hub
   python deploy/deploy_to_hf.py
   ```
   This creates the Space, stores the Groq key as a hidden secret, uploads the code, and prints the web address. The first build takes about 10 minutes.
5. *(Optional)* For automatic re-deploys whenever you push to GitHub, add two repository secrets on GitHub (Settings → Secrets and variables → Actions): `HF_TOKEN` and `GROQ_API_KEY`. The workflow in `.github/workflows/deploy.yml` then does step 4 for you.

Or with Docker anywhere:
```
docker build -t vnit-chatbot .
docker run -p 7860:7860 -e GENAI_API_KEY=<groq key> vnit-chatbot
```
Then open http://localhost:7860/.

---

## Repository layout

```
start_chatbot.bat      one-click start (Windows)
api/                   web server (FastAPI): chat page, /ask, /health, rate limiting
frontend/              chat page
pipeline/              crawling, document reading, chunking, indexing, search, answering, checks
data/raw/              collected text: web pages + doc_*.txt documents
data/documents/        list of all documents found, and what happened to each
deploy/                Hugging Face deploy script
docs/                  development history (every test round's instructions and report)
```

## Data and privacy note

All content comes from VNIT Nagpur's public website and the documents it links to; it belongs to VNIT. Documents listing individual students (names, roll numbers, phone numbers) are deliberately excluded. API keys are never stored in this repository.
