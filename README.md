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
- **Search:** sentence embeddings (`all-MiniLM-L6-v2`) + keyword search (TF-IDF), combined into 60 candidates, then re-ordered by a cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`). Candidates about a different degree programme or academic year than you asked about are set aside first — that is what tells 19 near-identical hostel fee sheets apart.
- **Answering:** Groq `openai/gpt-oss-20b`. If the AI can't be reached, the chatbot falls back to showing the best passages, and it always says which mode was used.
- **Follow-up questions:** ask "what is the hostel fee for first year B.Tech boys?" and then just "and for girls?" — the question is rewritten to stand on its own before searching, and the page shows "Understood as: …" so you can see how it was read.
- **Ratings:** every answer has a 👍/👎 button. Ratings are appended to `data/feedback/feedback.jsonl` (no IP addresses, and the file is kept out of git) so a demo week produces real usage data for the report.

---

## Project status (3 October 2026)

| Part | Status |
|---|---|
| Web pages | ✅ 81 pages from vnit.ac.in |
| Documents | ✅ **406 converted** — every usable document VNIT links: fee sheets, all 19 hostel fee sheets, academic calendars, scholarship notices, admission instructions, timetables, course books, department brochures, placement reports, Academic Rule Book. 599 links found, 456 selected after filters; of those, 33 excluded as lists of people, 5 had no readable text, 3 were Hindi-only and 7 failed (3 are dead links on vnit.ac.in) |
| Search index | ✅ 8,147 chunks |
| Answer quality | ✅ **17 of 18** test questions answered correctly end to end; both "impossible" questions correctly refused (details below) |
| Chat page | ✅ Works; one-click start with `start_chatbot.bat` (Windows) |
| Safety | ✅ Keys kept outside the project and never printed; per-visitor rate limit; answers can't inject code into the page; every converted document re-checked against the personal-data filter |
| Deployment | 🟡 **Public link from the laptop** with `start_public_link.bat` (free Cloudflare tunnel). Not always-online: Hugging Face now charges (PRO) for Docker Spaces, and free hosts with 512 MB of memory are too small (see "Deploying" below) |

### Measured quality

> **Being updated.** The 18-question check scored **17/18**. It has since been widened to **39 cases** (34 facts, 5 the chatbot must refuse, 2 follow-up conversations), which found four real bugs — all now fixed (see `EXPERIMENTS-LOG.md` §18–19). The widened suite last scored **31/39** before those fixes; the free Groq quota for the day ran out before it could be re-run. Retrieval is measurably better than when 17/18 was recorded (`chunk_ranks.py`: the answer passage reaches the AI for 29 of 32 questions), but **the end-to-end number below is from the 18-question round and should be re-measured** with `python check_answers.py` once the quota resets.

Three automatic checks, run on 3 Oct 2026 with all 406 documents included (previous round, 148 documents, in brackets):

| Check | What it measures | Result |
|---|---|---|
| `check_answers.py` | Asks the real chatbot 18 questions and checks each answer against facts verified by hand in the sources | **17/18 correct** (was 13/18) |
| (same) | Two questions whose answers are *not* in VNIT's material | **2/2 correctly refused** (no made-up answers) |
| `fact_ranks.py` | Is the passage containing the answer among the top 3 found? | 14/18 (was 12/18) |
| `evaluate.py` | Is the right *page or document* among the top 3? (19 questions) | **17/19 (89%)** (was 16/19) |

Answered correctly, among others:
- Civil Engineering intake (120/year) and the 5G lab announcement date (27 Oct 2023);
- Electrical M.Tech specialisations; the Director, the Registrar, the Dean (Academic)'s email;
- B.Tech tuition for the OPEN category (₹1,25,000/year) **and** for SC/ST (nil);
- the first-year B.Tech boys' hostel fee for Winter 2026 (₹32,150);
- the Kotak Kanya scholarship amount (₹1.5 lakh/year) and the IDFC scholarship deadline;
- when first-year classes start in Winter 2026 (19 Aug 2026) and when the end-semester exams run (7–15 Dec 2026).

Four of the five questions that failed in the previous round now pass, and the fifth (end-semester dates) is no longer partly wrong but correct.

**The one question that still fails:** the 2025-26 placement figures (678 students, 170 companies). They appear in a single paragraph of the T&P page, which is out-ranked by two placement reports whose company lists run to hundreds of passages. The chatbot says it cannot find them rather than quoting the 2024-25 numbers. Diagnosed in full in `EXPERIMENTS-LOG.md` §16.

Full answers are saved in `data/processed/answer_check.json`.

### Known limitations

- **One paragraph can lose to a long list.** The 2025-26 placement figures sit in one paragraph of the T&P page, while two placement reports contribute hundreds of company-list passages that match the same words. See `EXPERIMENTS-LOG.md` §16.
- **Designed posters.** A two-column poster can pair a label with the wrong value: the IDFC scholarship poster's "Application deadline" ended up next to the award amount, leaving the date on its own line. The chatbot declines rather than guessing which label owns the date.
- **Answers can vary slightly between runs**, because the AI model isn't perfectly repeatable. One test question passed in one run and failed in the next two with no change to the data.
- **Old documents** (e.g. 2024 calendars) are included. Each document's date is shown, the AI is told to prefer the newest, and passages about a different academic year than you asked about are now set aside — but a question about an old term could still get a stale answer.
- **Scanned PDFs** occasionally contain small OCR slips like "Nag pur".
- 15 documents could not be read at all: 7 failed (3 of them are dead links on vnit.ac.in), 5 had no readable text, 3 are Hindi-only.
- It only knows what was downloaded. Refreshing the data is manual (see `HOW-TO-RUN.md` §5).
- **Personal-data filtering is heuristic** (titles plus roll-number/student-email density). It excluded 33 documents, and all 406 converted documents were re-checked against it, but it is not a guarantee.

---

## What to do next

The chatbot itself is finished and working. What remains is optional:

1. **For the FYP report:** the numbers in "Measured quality", `EXPERIMENTS-LOG.md` (every change tried, with measurements — including the two that were measured and rejected) and `docs/development-history/` are ready-made evidence. §12 is a good story to tell: a parameter tuned on a small corpus (the reranking pool) silently became the biggest limit on accuracy once the corpus grew four times larger.
2. **Always-online hosting** (optional): replace PyTorch with the lighter ONNX runtime so the app fits a free 512 MB host such as Render, then re-run the three checks. Or pay for Hugging Face PRO and run `deploy/deploy_to_hf.py` unchanged. For a demo, `start_public_link.bat` already gives a public address from the laptop.
3. **Refresh the data** before the demo, if VNIT has posted new notices since 3 October 2026 — `HOW-TO-RUN.md` §5 has the commands. New documents are converted at roughly 1–3 minutes each.
4. **The remaining weak spots**, if there is time: a page-level retrieval stage would fix the placements question (see `EXPERIMENTS-LOG.md`, "Ideas not tried"), and reading two-column posters reliably would fix the IDFC-style layouts.
5. **Rotate the Groq key** after submission: it was pasted into a chat during development, so treat it as public. Create a new one at https://console.groq.com/keys and save it in `C:\Users\<you>\groq-key.txt`.

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
