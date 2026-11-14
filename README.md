# VNIT Chatbot

A chatbot that answers students' questions about **VNIT Nagpur** (admissions, fees, hostels, scholarships, notices, academic calendars, placements, departments, administration) using **only** the institute's own website and documents, and shows the source of every answer.

Final-year project (FYP). Built with free and open-source tools only.

> **How to start it and demo it:** see [`HOW-TO-RUN.md`](HOW-TO-RUN.md), written in plain language.
> **How it works in detail:** see [`APPLICATION.md`](APPLICATION.md).
> **What was tried and measured along the way:** see [`EXPERIMENTS-LOG.md`](EXPERIMENTS-LOG.md).

---

## What it does

- A student types a question in a chat page, for example *"What is the B.Tech tuition fee?"* or *"When do first-year classes start in Winter 2026?"*
- The chatbot searches VNIT's web pages and documents, picks the most relevant passages, and **grades its own search**: if the passages look weak, it looks inside the best-titled pages before going on. An **AI agent** (Groq, free tier) then reads them and decides: answer now, or **act** — search again with other words, find a specific document by its title and look inside it, look up a row in one of the documents' tables, or calculate a total. It then writes a short answer **using only what it found**, with numbered links to the sources.
- If a question fits several groups of students (*"What is the hostel fee?"* — for which programme? boys or girls?), it **asks back with buttons** instead of guessing.
- Before the answer is shown, a **verifier** checks every figure, date, email and phone number in it against the documents the agent read. Anything it can't confirm is sent back for one rewrite, and if it still can't be confirmed, the answer says so.
- Under each answer, **"How I found this"** lists every step the agent took, so you can check its reasoning instead of trusting it.
- If the answer isn't in VNIT's material, it **says so instead of making something up**, and adds **who can help**: the right VNIT office's email and phone, copied from VNIT's own contact pages. In every test round so far, it has never invented an answer.

## How it works (short version)

```
 vnit.ac.in pages ─┐                                   ┌─ hybrid search (meaning + keywords)
                   ├─► plain text ─► ~150-word chunks ─┤─ reranker picks the best passages
 Google Drive PDFs ┘   (Docling: tables, scans)        └─ search grade ─► (ask back?) ─┐
 (notices, fee sheets, calendars)    │                    weak: look inside the       │
                                     └─► table rows        best-titled pages          │
                                         (SQLite)                                     ▼
                       chat page ◄─ "who can help" ◄─ verifier ◄─────────────── AI agent
                                    (only if it                                   │  ▲
                                     can't answer)          tools: search again, find a document,
                                                            look inside it, look up a table row,
                                                            calculate (up to 2 rounds)
```

- **Web pages:** a polite crawler (1 request per second, respects robots.txt).
- **Documents:** most VNIT notices are PDFs on Google Drive. They're downloaded through the official Google Drive API and read with **Docling**, which understands page layout, keeps tables as proper rows and reads scanned pages (OCR).
- **Privacy:** lists of people (seating plans, merit lists, class-committee lists with phone numbers) are **excluded**, both by title and by checking the content for student roll numbers.
- **Search:** sentence embeddings (`all-MiniLM-L6-v2`) + keyword search (TF-IDF), combined into 60 candidates, then re-ordered by a cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`). Candidates about a different degree programme or academic year than you asked about are set aside first — that is what tells 19 near-identical hostel fee sheets apart.
- **Routing** (`pipeline/router.py`): greetings, "what can you do?" and clearly off-topic requests get an instant fixed reply, with no search and no AI cost. Every other question is also given a topic (fees, hostel, calendar, scholarship, placement, admission, people, department, rules), used to pick the right office for the hand-off.
- **Search grade** (`pipeline/grader.py`, a "corrective RAG" step): plain code scores the first search from the reranker's scores and how many of the question's rare words the best passages contain: correct, ambiguous or incorrect. When it is not "correct", the passages inside the best-titled pages are added before the AI is asked. This is what fixed the 2025-26 placement totals.
- **The agent** (`pipeline/planner.py`, `tools.py`): Groq `openai/gpt-oss-120b` with function calling (the fallback uses `gpt-oss-20b`, which has its own free daily allowance, so one running out does not stop the other). It starts from the tuned search results and may call five tools: `search_vnit`, `find_documents`, `read_document` (search inside one page or document), `lookup_table` (one row of a fee sheet or timetable, from the 23,088 table rows kept in `data/processed/facts.db`, built by `build_facts.py`) and `calculate`. It gets up to 2 rounds, and paces itself to stay within the free plan's 8,000 tokens a minute.
- **The verifier** (`pipeline/verifier.py`): plain code, not another AI call, so it is free and gives the same result every time. It checks each figure, date, email and phone number against the passages actually shown, sends unsupported ones back for one revision, and flags anything still unconfirmed. The chat page shows a ✓ or ⚠ badge.
- **Fallback:** if the agent can't run, the answer is written in one step from the same search; if the AI can't be reached at all, the best passages are shown. The page always says which mode was used.
- **Follow-up questions:** ask "what is the hostel fee for first year B.Tech boys?" and then just "and for girls?" — the question is rewritten to stand on its own before searching, and the page shows "Understood as: …" so you can see how it was read.
- **Clarifying questions** (`pipeline/slots.py`): ask "What is the hostel fee?" and the chatbot asks which programme, then boys or girls, with buttons, because VNIT publishes a different fee sheet for each. It remembers your choices for the rest of the chat (in the page only, never on the server), and "Clear my details" forgets them. It only asks when the documents it found really differ; none of the 39 test questions is asked back.
- **"Who can help":** when the chatbot can't answer, or the verifier can't confirm the answer, it adds the right VNIT office's email and phone for the question's topic (hostel, accounts, academics, Director's office, Registrar), from `data/contacts.json`, which was checked by hand against VNIT's contact pages.
- **Ratings:** every answer has a 👍/👎 button. Ratings are appended to `data/feedback/feedback.jsonl` (no IP addresses, and the file is kept out of git) so a demo week produces real usage data for the report.

---

## Project status (14 November 2026)

| Part | Status |
|---|---|
| Web pages | ✅ 81 pages from vnit.ac.in |
| Documents | ✅ **406 converted** — every usable document VNIT links: fee sheets, all 19 hostel fee sheets, academic calendars, scholarship notices, admission instructions, timetables, course books, department brochures, placement reports, Academic Rule Book. 599 links found, 456 selected after filters; of those, 33 excluded as lists of people, 5 had no readable text, 3 were Hindi-only and 7 failed (3 are dead links on vnit.ac.in) |
| Search index | ✅ 8,162 chunks |
| Answer quality | ✅ **37 of 39** test questions answered correctly by the agent, plus **4 of 4** clarifying-question cases (41/43 in all); all 5 "impossible" questions correctly refused. These saved results were collected over several runs on 30 Oct as fixes landed; one uninterrupted full run is being measured now (details below) |
| Agentic layer | ✅ **Added 30 October 2026**: a router (kind of question and topic), a corrective search gate that grades the first search and looks inside the best-titled pages when it is weak, clarifying questions with buttons when a question fits several groups ("What is the hostel fee?" → B.Tech? → Girls?), remembered for the rest of the chat, a "Who can help" office contact when the answer isn't in VNIT's documents, a planner with five tools (search again, find a document, look inside it, look up a table row, calculate), and a verifier that checks every figure before an answer is shown, with one automatic revision. Every step is visible in the chat page. 54/54 automated tests pass (`pipeline/test_agentic.py`, no key needed) |
| Measuring each piece | 🟡 **In progress** (started 30 Oct, restarted 14 Nov): `pipeline/run_ablations.sh` switches the pieces on one at a time on 14 hard questions, then makes one full run of all 43 cases. It runs unattended, waiting for the free daily allowance to refill, and takes several more days. The one-shot baseline is finished. Results so far: `EXPERIMENTS-LOG.md` §26 |
| Chat page | ✅ Works; one-click start with `start_chatbot.bat` (Windows). Shows "How I found this", a ✓/⚠ verification badge and numbered citations |
| Safety | ✅ Keys kept outside the project and never printed; per-visitor rate limit; answers can't inject code into the page; every converted document re-checked against the personal-data filter |
| Deployment | 🟡 **Public link from the laptop** with `start_public_link.bat` (free Cloudflare tunnel). Not always-online: Hugging Face now charges (PRO) for Docker Spaces, and free hosts with 512 MB of memory are too small (see "Deploying" below) |

### Measured quality

Measured from 30 October to 8 November 2026, with every answer coming from the pipeline being measured (no quota fallbacks counted):

| Check | What it measures | Result |
|---|---|---|
| `check_answers.py` (agent) | Asks the real chatbot **39 questions** (34 facts verified by hand in the sources, 5 it must refuse, 2 follow-up conversations) and **4 clarifying-question cases** through the same path as the chat page | **37/39 correct + 4/4 clarify cases** (41/43). The last uninterrupted full run, before the search grade, scored 35/39 |
| (same) | The 5 questions whose answers are *not* in VNIT's material | **5/5 correctly refused** (no made-up answers) |
| (same) | How often the agent decided to use tools | 7 of the 43 saved answers |
| `check_answers.py --pipeline oneshot` | The same 43 cases through the older one-search, one-call pipeline (finished 8 Nov) | **34/39 + 4/4** (38/43). It misses the placement totals, the summer-term fee and the B.Arch fee, which the agent finds by opening documents |
| `ablation_table.py` | What each piece adds, on 14 hard questions | being measured (`EXPERIMENTS-LOG.md` §26) |
| `test_agentic.py` | Intent, search grade, clarifying questions, hand-off, table lookup, the tools, the verifier and the decision loop (no key needed) | **54/54** |
| `chunk_ranks.py` | Does the passage holding the answer reach the AI? (32 questions) | 29/32 |
| `fact_ranks.py` | Is the passage containing the answer among the top 3 found? | 15/18 |
| `evaluate.py` | Is the right *page or document* among the top 3? (19 questions) | 16/19 |

The 2025-26 placement totals (678 students, 170 companies) failed in the full run because the agent opened the placement report instead of the T&P page. The search grade now scores that first search (−1.2, far below the ~7 of a good match), looks inside the best-titled page the search missed, and finds the figures there before the AI is asked: it passes on re-test (`EXPERIMENTS-LOG.md` §22). B.Arch tuition also passes now (the agent found ₹1,25,000 in the JoSAA fee document). Two still fail: M.Sc tuition (OCR damage: the OPEN-category fee row lost its label, and the agent stops at the SC/ST row) and slot A's mid-sem, which turned out to be ambiguous: 1 Oct for first-year students, 4 Sept for higher semesters, and the question doesn't say which (`EXPERIMENTS-LOG.md` §25). Earlier rounds: 17/18 on the original 18-question check (3 Oct), 13/18 before that.

Answered correctly, among others:
- Civil Engineering intake (120/year) and the 5G lab announcement date (27 Oct 2023);
- Electrical M.Tech specialisations; the Director, the Registrar, the Dean (Academic)'s email;
- B.Tech tuition for the OPEN category (₹1,25,000/year) **and** for SC/ST (nil);
- the first-year B.Tech boys' hostel fee for Winter 2026 (₹32,150);
- the Kotak Kanya scholarship amount (₹1.5 lakh/year) and the IDFC scholarship deadline;
- when first-year classes start in Winter 2026 (19 Aug 2026) and when the end-semester exams run (7–15 Dec 2026).

Also answered correctly by the agent: the girls' hostel fee (₹32,650), the summer-term fee per course (₹3,000, which failed in the previous round: the agent opened the Summer Term 2026 notice to find it), the anti-ragging helpline, convocation and re-exam dates, M.Tech tuition, and both follow-up conversations.

Full answers, each with its steps and verification, are saved in `data/processed/answer_check.json` (agent) and `answer_check_oneshot.json` (baseline), and each measured configuration in `answer_check_<name>.json`.

### Known limitations

- **One paragraph can lose to a long list.** The 2025-26 placement figures sit in one paragraph of the T&P page, while two placement reports contribute hundreds of company-list passages that match the same words. See `EXPERIMENTS-LOG.md` §16.
- **The agent doesn't always pick the best page to open by itself.** For the placement totals it opened the placement report instead of the T&P page (`EXPERIMENTS-LOG.md` §20c). The search grade now does that lookup as code when the first search looks weak (§22), but its thresholds were calibrated on this project's 37 test questions, so other weak searches may slip past it.
- **The table lookup tool has not been used by the agent in a live run yet.** It works when called (tested on the fee sheets), but so far the agent has preferred to search and read instead (`EXPERIMENTS-LOG.md` §25).
- **When the agent's free daily allowance runs out, answers quietly fall back** to the simpler one-shot pipeline. The page says so ("mode"), but such answers are less thorough. The test harness once counted them as agent answers by mistake; it no longer does (`EXPERIMENTS-LOG.md` §26).
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

The chatbot itself is finished and working. What remains:

1. **Let the measurements finish.** `run_ablations.sh` runs in its own minimized window; keep the laptop on and awake. If it stops (a restart, closing the window), start it again from Git Bash in the `pipeline` folder with `bash run_ablations.sh`: it never asks a question twice. Using the chatbot meanwhile spends the same daily allowance and slows it down. When the log (`data/processed/ablation_runs.log`) says "all tracks done", the final numbers go into this README, `EXPERIMENTS-LOG.md` §26, `APPLICATION.md` and slides 16–19.
2. **Decide on the slot-A question:** either the chatbot asks which year of study you're in for timetable questions, or the test question is reworded to say "first year". Both answers it found are right for someone.
3. **For the FYP report:** the numbers in "Measured quality", `EXPERIMENTS-LOG.md` (every change tried, with measurements — including the ones measured and rejected, and three faults in the test harness itself) and `docs/development-history/` are ready-made evidence. §12 is a good story to tell: a parameter tuned on a small corpus (the reranking pool) silently became the biggest limit on accuracy once the corpus grew four times larger.
4. **Always-online hosting** (optional): replace PyTorch with the lighter ONNX runtime so the app fits a free 512 MB host such as Render, then re-run the checks. Or pay for Hugging Face PRO and run `deploy/deploy_to_hf.py` unchanged. For a demo, `start_public_link.bat` already gives a public address from the laptop.
5. **Refresh the data** before the demo, if VNIT has posted new notices since 3 October 2026 — `HOW-TO-RUN.md` §5 has the commands (including `build_facts.py` for the table rows). New documents are converted at roughly 1–3 minutes each.
6. **The remaining weak spot**, if there is time: the M.Sc fee table damaged by OCR. Reading two-column posters reliably would fix the IDFC-style layouts.
7. **Rotate the Groq key** after submission: it was pasted into a chat during development, so treat it as public. Create a new one at https://console.groq.com/keys and save it in `C:\Users\<you>\groq-key.txt`.

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
start_public_link.bat  the same, plus a temporary public address (Cloudflare tunnel)
api/                   web server (FastAPI): chat page, /ask, /feedback, /health, rate limiting
frontend/              chat page (answers, "How I found this", clarify buttons, ratings)
pipeline/
  crawl.py, recrawl.py, ingest_documents.py, doc_convert.py, drive_utils.py
                       collecting web pages and documents, reading PDFs with Docling
  chunk.py, build_index.py, build_facts.py
                       passages, the search index, the table rows (facts.db)
  query.py, programme_terms.py
                       hybrid search, reranking, setting aside other programmes/years
  respond.py           one question from start to finish: router, slots, search grade,
                       agent, hand-off (the chat page calls this)
  router.py, grader.py, slots.py, planner.py, tools.py, verifier.py, followup.py, generate.py
                       the pieces it uses
  check_answers.py, chunk_ranks.py, fact_ranks.py, evaluate.py, test_agentic.py
                       the checks in "Measured quality"
  run_ablations.sh, ablation_table.py, grade_calibration.py, feedback_summary.py
                       measuring each piece, calibrating the grade, summarising ratings
data/raw/              collected text: web pages + doc_*.txt documents
data/documents/        list of all documents found, and what happened to each
data/processed/        search index, table rows, and every saved test run
data/contacts.json     VNIT office contacts for "Who can help", checked by hand
deploy/                Hugging Face deploy script
docs/                  development history (every test round's instructions and report)
HOW-TO-RUN.md          plain-language start, demo and troubleshooting guide
APPLICATION.md         how it works in detail
EXPERIMENTS-LOG.md     every change tried, with measurements
REPORT8.md, RUNBOOK-7-AGENTIC-UPGRADES.md, AGENTIC-UPGRADE-PLAN.md
                       the latest round's plan, instructions and report
```

## Data and privacy note

All content comes from VNIT Nagpur's public website and the documents it links to; it belongs to VNIT. Documents listing individual students (names, roll numbers, phone numbers) are deliberately excluded. API keys are never stored in this repository.
