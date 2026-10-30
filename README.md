# VNIT Chatbot

A chatbot that answers students' questions about **VNIT Nagpur** (admissions, fees, hostels, scholarships, notices, academic calendars, placements, departments, administration) using **only** the institute's own website and documents, and shows the source of every answer.

Final-year project (FYP). Built with free and open-source tools only.

> **How to start it and demo it:** see [`HOW-TO-RUN.md`](HOW-TO-RUN.md), written in plain language.
> **How it works in detail:** see [`APPLICATION.md`](APPLICATION.md).
> **What was tried and measured along the way:** see [`EXPERIMENTS-LOG.md`](EXPERIMENTS-LOG.md).

---

## What it does

- A student types a question in a chat page, for example *"What is the B.Tech tuition fee?"* or *"When do first-year classes start in Winter 2026?"*
- The chatbot searches VNIT's web pages and documents, picks the most relevant passages, and an **AI agent** (Groq, free tier) reads them and decides: answer now, or **act** — search again with other words, find a specific document by its title and look inside it, or calculate a total. It then writes a short answer **using only what it found**, with numbered links to the sources.
- Before the answer is shown, a **verifier** checks every figure, date, email and phone number in it against the documents the agent read. Anything it can't confirm is sent back for one rewrite, and if it still can't be confirmed, the answer says so.
- Under each answer, **"How I found this"** lists every step the agent took, so you can check its reasoning instead of trusting it.
- If the answer isn't in VNIT's material, it **says so instead of making something up**, and adds **who can help**: the right VNIT office's email and phone, copied from VNIT's own contact pages. In every test round so far, it has never invented an answer.

## How it works (short version)

```
 vnit.ac.in pages ─┐                                   ┌─ hybrid search (meaning + keywords)
                   ├─► plain text ─► ~150-word chunks ─┤─ reranker picks the best passages
 Google Drive PDFs ┘   (Docling: tables, scans)        └─ AI agent ─► verifier ─► chat page
 (notices, fee sheets, calendars)                          │  ▲
                                          tools: search again, find a document,
                                          look inside it, calculate (up to 2 rounds)
```

- **Web pages:** a polite crawler (1 request per second, respects robots.txt).
- **Documents:** most VNIT notices are PDFs on Google Drive. They're downloaded through the official Google Drive API and read with **Docling**, which understands page layout, keeps tables as proper rows and reads scanned pages (OCR).
- **Privacy:** lists of people (seating plans, merit lists, class-committee lists with phone numbers) are **excluded**, both by title and by checking the content for student roll numbers.
- **Search:** sentence embeddings (`all-MiniLM-L6-v2`) + keyword search (TF-IDF), combined into 60 candidates, then re-ordered by a cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`). Candidates about a different degree programme or academic year than you asked about are set aside first — that is what tells 19 near-identical hostel fee sheets apart.
- **Routing:** greetings, "what can you do?" and clearly off-topic requests get an instant fixed reply, with no search and no AI cost.
- **The agent** (`pipeline/planner.py`, `tools.py`): Groq `openai/gpt-oss-120b` with function calling (the fallback uses `gpt-oss-20b`, which has its own free daily allowance, so one running out does not stop the other). It starts from the tuned search results and may call four tools: `search_vnit`, `find_documents`, `read_document` (search inside one page or document), and `calculate`. It gets up to 2 rounds, and paces itself to stay within the free plan's 8,000 tokens a minute.
- **The verifier** (`pipeline/verifier.py`): plain code, not another AI call, so it is free and gives the same result every time. It checks each figure, date, email and phone number against the passages actually shown, sends unsupported ones back for one revision, and flags anything still unconfirmed. The chat page shows a ✓ or ⚠ badge.
- **Fallback:** if the agent can't run, the answer is written in one step from the same search; if the AI can't be reached at all, the best passages are shown. The page always says which mode was used.
- **Follow-up questions:** ask "what is the hostel fee for first year B.Tech boys?" and then just "and for girls?" — the question is rewritten to stand on its own before searching, and the page shows "Understood as: …" so you can see how it was read.
- **Clarifying questions:** ask "What is the hostel fee?" and the chatbot asks which programme, then boys or girls, with buttons, because VNIT publishes a different fee sheet for each. It remembers your choices for the rest of the chat (in the page only, never on the server), and "Clear my details" forgets them. It only asks when the documents it found really differ; none of the 39 test questions is asked back.
- **Ratings:** every answer has a 👍/👎 button. Ratings are appended to `data/feedback/feedback.jsonl` (no IP addresses, and the file is kept out of git) so a demo week produces real usage data for the report.

---

## Project status (30 October 2026)

| Part | Status |
|---|---|
| Web pages | ✅ 81 pages from vnit.ac.in |
| Documents | ✅ **406 converted** — every usable document VNIT links: fee sheets, all 19 hostel fee sheets, academic calendars, scholarship notices, admission instructions, timetables, course books, department brochures, placement reports, Academic Rule Book. 599 links found, 456 selected after filters; of those, 33 excluded as lists of people, 5 had no readable text, 3 were Hindi-only and 7 failed (3 are dead links on vnit.ac.in) |
| Search index | ✅ 8,162 chunks |
| Answer quality | ✅ **35 of 39** test questions answered correctly end to end by the agent in the last full run; all 5 "impossible" questions correctly refused. Since then the placement question has been fixed (corrective search gate) and passes on re-test, so the saved results read **36/39** (details below) |
| Agentic layer | ✅ **Added 30 October 2026**: a router (kind of question and topic), a corrective search gate that grades the first search and looks inside the best-titled pages when it is weak, clarifying questions with buttons when a question fits several groups ("What is the hostel fee?" → B.Tech? → Girls?), remembered for the rest of the chat, a "Who can help" office contact when the answer isn't in VNIT's documents, a planner with five tools (search again, find a document, look inside it, look up a table row, calculate), and a verifier that checks every figure before an answer is shown, with one automatic revision. Every step is visible in the chat page. 53/53 automated tests pass (`pipeline/test_agentic.py`, no key needed) |
| Chat page | ✅ Works; one-click start with `start_chatbot.bat` (Windows). Shows "How I found this", a ✓/⚠ verification badge and numbered citations |
| Safety | ✅ Keys kept outside the project and never printed; per-visitor rate limit; answers can't inject code into the page; every converted document re-checked against the personal-data filter |
| Deployment | 🟡 **Public link from the laptop** with `start_public_link.bat` (free Cloudflare tunnel). Not always-online: Hugging Face now charges (PRO) for Docker Spaces, and free hosts with 512 MB of memory are too small (see "Deploying" below) |

### Measured quality

Measured on 30 October 2026, with every question reaching the AI (no quota fallbacks in the results):

| Check | What it measures | Result |
|---|---|---|
| `check_answers.py` (agent) | Asks the real chatbot **39 questions** (34 facts verified by hand in the sources, 5 it must refuse, 2 follow-up conversations) through the same path as the chat page | **35/39 correct** in the full run of 30 Oct; **36/39** saved after the placement fix was re-tested |
| (same) | The 5 questions whose answers are *not* in VNIT's material | **5/5 correctly refused** (no made-up answers) |
| (same) | How often the agent decided to use tools | 9 of 39 questions |
| `check_answers.py --pipeline oneshot` | The same questions through the older one-search, one-call pipeline | being measured: 19/20 so far, the same as the agent on those 20 (see `EXPERIMENTS-LOG.md` §20f) |
| `test_agentic.py` | The agent's tools, the verifier and the decision loop (no key needed) | **53/53** |
| `chunk_ranks.py` | Does the passage holding the answer reach the AI? (32 questions) | 29/32 |
| `fact_ranks.py` | Is the passage containing the answer among the top 3 found? | 15/18 |
| `evaluate.py` | Is the right *page or document* among the top 3? (19 questions) | 16/19 |

The 2025-26 placement totals (678 students, 170 companies) failed in the full run because the agent opened the placement report instead of the T&P page. A corrective search gate now grades the first search (it scored −1.2, far below the ~7 of a good match), looks inside the best-titled page the search missed, and finds the figures there before the AI is asked: it passes on re-test (`EXPERIMENTS-LOG.md` §22). Since then B.Arch tuition also passes (the agent found ₹1,25,000 in the JoSAA fee document). Two still fail: M.Sc tuition (OCR damage: the OPEN-category fee row lost its label, and the agent stops at the SC/ST row) and slot A's mid-sem, which turned out to be ambiguous: 1 Oct for first-year students, 4 Sept for higher semesters, and the question doesn't say which (`EXPERIMENTS-LOG.md` §25). Before that, the weak spots were: the M.Sc and B.Arch tuition (the scanned fee tables lost their labels in OCR), and one exam slot's mid-sem date (timetable rows split across passages). Earlier rounds: 17/18 on the original 18-question check (3 Oct), 13/18 before that.

Answered correctly, among others:
- Civil Engineering intake (120/year) and the 5G lab announcement date (27 Oct 2023);
- Electrical M.Tech specialisations; the Director, the Registrar, the Dean (Academic)'s email;
- B.Tech tuition for the OPEN category (₹1,25,000/year) **and** for SC/ST (nil);
- the first-year B.Tech boys' hostel fee for Winter 2026 (₹32,150);
- the Kotak Kanya scholarship amount (₹1.5 lakh/year) and the IDFC scholarship deadline;
- when first-year classes start in Winter 2026 (19 Aug 2026) and when the end-semester exams run (7–15 Dec 2026).

Also answered correctly by the agent: the girls' hostel fee (₹32,650), the summer-term fee per course (₹3,000, which failed in the previous round: the agent opened the Summer Term 2026 notice to find it), the anti-ragging helpline, convocation and re-exam dates, M.Tech tuition, and both follow-up conversations.

Full answers, each with its steps and verification, are saved in `data/processed/answer_check.json` (agent) and `answer_check_oneshot.json` (baseline).

### Known limitations

- **One paragraph can lose to a long list.** The 2025-26 placement figures sit in one paragraph of the T&P page, while two placement reports contribute hundreds of company-list passages that match the same words. See `EXPERIMENTS-LOG.md` §16.
- **The agent doesn't always pick the best page to open by itself.** For the placement totals it opened the placement report instead of the T&P page (`EXPERIMENTS-LOG.md` §20c). The corrective search gate now does that lookup as code when the first search looks weak (§22), but its thresholds were calibrated on this project's 37 test questions, so other weak searches may slip past it.
- **Questions that need extra lookups are slower** on the free plan: 30–70 seconds instead of a few, because the agent waits for the per-minute allowance rather than fail.
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
4. **The remaining weak spots**, if there is time: the M.Sc and B.Arch fee tables damaged by OCR, and the slot-A mid-sem row. Reading two-column posters reliably would fix the IDFC-style layouts.
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
pipeline/              crawling, document reading, chunking, indexing, search, the agent
                       (respond, router, planner, tools, verifier), answering, checks
data/raw/              collected text: web pages + doc_*.txt documents
data/documents/        list of all documents found, and what happened to each
deploy/                Hugging Face deploy script
docs/                  development history (every test round's instructions and report)
```

## Data and privacy note

All content comes from VNIT Nagpur's public website and the documents it links to; it belongs to VNIT. Documents listing individual students (names, roll numbers, phone numbers) are deliberately excluded. API keys are never stored in this repository.
