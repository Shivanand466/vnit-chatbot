# APPLICATION.md — VNIT Website Chatbot: technical reference

What this application is, how it works, what's verified (with measured numbers), and the reasons behind its design. For **starting and demoing** it, see `HOW-TO-RUN.md`. For the evidence behind each design choice, see `EXPERIMENTS-LOG.md`.

---

## 1. What it is

A chatbot that answers students' questions about VNIT Nagpur using **only** the institute's own website and documents, with a source link for every answer. It covers admissions, fees, hostels, scholarships, notices, academic calendars, placements, departments and administration.

**Constraints that shaped every decision:**
- **Zero budget.** Free and open-source only. The LLM is Groq's free API; retrieval runs locally.
- **Honesty over coverage.** When the answer isn't in its sources, it must say so, never guess.

**In one sentence:** crawl the website and its linked documents into plain text → split into ~150-word chunks → index them two ways (meaning and keywords) → for each question, find candidate chunks with hybrid search and a reranker, then hand them to an **agent** that decides whether they answer the question or whether to act (search again, open a specific document, calculate), writes a cited answer, and has every figure in it **verified** against the sources → serve it through a small web API and chat page that shows each step.

---

## 2. Status (as of 2026-11-20, evening; index frozen as tag `final-index-2026-11-20`)

| Part | Status |
|---|---|
| Web pages | **81** pages crawled from vnit.ac.in are searched. The website project's full crawl (814 usable pages) is kept in `data/raw_site_crawl/` but not searched: measured on 20 Nov, it brought no test answer to the AI and pushed some out (EXPERIMENTS-LOG §29) |
| Documents (PDF notices, fee sheets, calendars…) | **448 searched** (`data/raw/doc_*.txt`). 406 from the first crawl's 599 links. 42 more on 20 Nov from the website project's full crawl: `ingest_documents.py discover-crawl` added 116 documents to the inventory, 53 were processed before the 4-hour timebox and 62 are still to do. 4 are held in `data/raw_new_docs_held/` because they pushed answers out (EXPERIMENTS-LOG §34). In `status.json`: 34 lists of people, 6 no readable text, 4 Hindi-only, 18 failed or timed out. Re-run `ingest_documents.py convert --only-new`; it skips finished ones |
| Chunks in the index | **7,328** (a table's lead-in written once per group of rows, EXPERIMENTS-LOG §30); 31,682 table cells in `facts.db` (rows of tables without a lead-in included since §35) |
| Retrieval | Title-prefixed chunks → hybrid (sentence embeddings + TF-IDF keywords) → programme/year contradiction filter → 60-candidate cross-encoder reranking → a passage repeating one ranked above it (over 90% of words in common) is left out → up to 5 passages per (sub-)question |
| Page-level benchmark (`evaluate.py`, 19 questions) | 16/19 |
| Answer-chunk ranks (`fact_ranks.py`) | **13/18** (15/18 before 20 Nov; the Kotak Kanya question is now 4th, behind its own 2026-27 notice, §34) |
| Real-path retrieval (`chunk_ranks.py`, the 82 answerable questions of the 105, through `agent.answer`) | **78/82** have the answer-bearing passage among the 7 sent to the LLM (the earlier 77: 73/77; 69/77 before 20 Nov); 71/82 in the top 3 |
| Evidence the agent starts from (`evidence_check.py`: `respond.answer` with a stand-in planner, corrective passages included) | **80/82** fact questions and **11/11** conversation and profile cases (73/77 and 10/11 before Runbook 10) |
| End-to-end answer check (`check_answers.py`, 105 cases since 20 Nov, EXPERIMENTS-LOG §27, §34) | **105/105** saved results through the agent (20 Nov evening; 97/100 after EXPERIMENTS-LOG §30-§33, 91/100 before). The last three failures (Holi, the 2024-25 company count, Ph.D. part-time tuition) pass since the corrective step adds table rows (§35, §36). A fresh full run of all 105 on the frozen index is being measured by `run_ablations.sh` (`answer_check_full.json`). Earlier, on the original 39 cases: 35/39 in the full run of 2026-10-30 |
| LLM | Groq free tier: `openai/gpt-oss-120b` for the agent, `openai/gpt-oss-20b` for the one-shot fallback and follow-up rewriting (separate daily allowances, §5a) |
| Agentic layer (added 2026-10-30) | Router (kind of message, and topic: fees, hostel, calendar, …) → follow-up resolver → first search → **clarify or assume** (slots.py: asks which programme/gender when the relevant passages carry different figures for different groups, or fills it from the chat's profile) → **corrective gate** (grades the first search from the reranker's scores; if weak, looks inside the 2 best-titled pages it missed) → **planner** with five tools (`search_vnit`, `find_documents`, `read_document`, `lookup_table`, `calculate`), up to 2 rounds → **verifier** (every figure, date, email and phone number checked against the passages shown) → one revision if anything is unsupported → **hand-off**: a refusal or unconfirmed answer gets the right office's contact (`data/contacts.json`). Falls back to the one-shot pipeline if the agent cannot run. See §5a |
| Agent tests (`test_agentic.py`, no key needed) | **112/112** on `agent-v2` (v1's 73, which also pass with `AGENT_V2=off`, plus 39 for v2 in `test_agent_v2.py`) |
| API + chat page | Working; one-click start via `start_chatbot.bat`, verified live on 2026-10-30. Follow-up questions ("and for girls?"), a "How I found this" panel listing the agent's steps, a verification badge, numbered citations, and a thumbs up/down rating on every answer |
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
│       ├── answer_check.json  <- last end-to-end answer check (agent pipeline)
│       └── answer_check_oneshot.json <- same questions, one-shot pipeline (baseline)
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
    ├── query.py               <- hybrid search + contradiction filter + reranking;
    │                             document catalogue and search-inside-one-document
    ├── agent.py               <- splits compound questions, retrieves per part and whole
    ├── router.py              <- greeting / capability / out-of-scope / lookup, before any search
    ├── respond.py             <- the one entry point: resolve → route → search → agent → verify
    ├── planner.py             <- the agent: decides, calls tools, answers, revises once
    ├── tools.py               <- the agent's tools + the numbered evidence log ([P1], [P2]…)
    ├── verifier.py            <- checks every figure/date/email/phone against the passages
    ├── generate.py            <- one-shot prompt, shared answer rules, extractive fallback
    ├── test_agentic.py        <- 54 tests for intent, the search grade, slots, hand-off, table lookup, tools, verifier, agent loop and the answer check's quota handling (no key needed)
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

Everything goes through `respond.answer` (the API and `check_answers.py` alike). Before any search, `router.route` decides what kind of message it is: a greeting, thanks, "what can you do?" or an obviously out-of-scope request gets a fixed reply with no search and no LLM call; anything else is a lookup, and `router.intent` tags it with a topic (`fees`, `hostel`, `calendar`, `scholarship`, `placement`, `admission`, `people`, `department`, `rules` or `other`; keyword patterns in a fixed priority order, no LLM call), shown in the trace as "Topic: …". A lookup runs steps 0–2 below (the first search), then the agent of §5a. Step 3 is the one-shot composer, which is now the agent's fallback and the measured baseline.

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

### 5a. The agent: plan, act, verify (`planner.py`, `tools.py`, `verifier.py`)

The one-shot pipeline searched once and printed whatever the LLM wrote. When that search missed, it could only say "not found", and nothing checked the answer it did give. The agent adds both:

```
 first search (steps 0-2) ──► agent reads the passages ──► answer? ──yes──► verify ──ok──► reply
                                    ▲                        │ no                 │ unsupported
                                    │                        ▼                    ▼
                                    └──── observe ◄──── call tools          revise once, re-verify;
                                     (up to 2 rounds)  search_vnit           still unsupported →
                                                       find_documents        visible warning
                                                       read_document
                                                       calculate
```

**A. Clarify or assume** (`slots.py`, no LLM). Topics that need details (hostel: programme and gender; fees: programme and category; calendar: programme) are checked against the question and the profile the chat page sends. A missing detail is filled from the profile ("Assuming B.Tech girls, from earlier in this chat."), or, if the relevant first-search passages (rerank ≥ 3.0) hold two or more different values for it *and* those groups' best passages carry different figures or dates, the student is asked with 2–4 buttons (`mode: "clarify"`, no LLM call). A fee question naming no programme is also asked when the 10 best-titled documents are fee sheets for 3 or more programmes. Of the 100 test cases, only the two deliberately vague ones are asked back (EXPERIMENTS-LOG §23, §31). `CLARIFY=off` disables it; the profile is never stored.

**B. Grade** (`grader.py`, Corrective RAG, no LLM). The first search is graded from the cross-encoder's best score for the whole question (`top`) and the share of the question's rarer words and academic year found in the top 3 passages (`coverage`): `correct` if top ≥ 3.0 and coverage ≥ 0.75, `incorrect` if top < 0, otherwise `ambiguous` (always, if a named academic year is in none of the top 3). Thresholds were calibrated on the test questions (`grade_calibration.py`, EXPERIMENTS-LOG §22). When the grade is not `correct`, `respond.corrective_passages` looks inside the 2 best-titled pages the first search did not reach and adds each one's best passage if it scores above 0; the model is also told `Search quality: <grade> (<why>)`. This is the lookup the planner did not choose by itself for the placement figures. For fees, calendar and placement questions, `respond.table_rows` also adds the 2 best table rows from `facts.db`, whatever the grade. The keywords are the question's rarer words; the filters are its programme, gender, category, year and academic year. A row needs at least 2 of those words, is ranked by the rare words in its own label and cells, is taken at most once per document, and is capped at 450 characters. This is how a single row of a long table reaches the agent when other rows of the same table fill its places in the passage search (EXPERIMENTS-LOG §35). `CRAG_GATE=off` disables both; the one-shot fallback does not use them.

1. **Observe.** The first search's passages — exactly the ones the one-shot path would send — go to the LLM, labelled `[P1]`, `[P2]`… with the document each comes from (`doc S57`). Below them is a short list of pages whose *titles* match the question, so the agent can see a relevant page even when none of its paragraphs ranked.
2. **Decide.** If the passages answer the question, the agent answers straight away: one LLM call, the same cost as before. Otherwise it acts.
3. **Act** with four tools (OpenAI-style function calling, which Groq supports):
   - `search_vnit(query)` — search everything again with other words (3 passages back);
   - `find_documents(keywords)` — find pages/documents by title. Titles are matched on word stems weighted by rarity (so "placement" counts for far more than "students"), with the academic year and the programme/year/gender contradiction filter of `programme_terms.py` applied to titles too;
   - `read_document(document_id, query)` — search *inside one* page or document (`query.retrieve_within`). This is the page-level stage EXPERIMENTS-LOG §16 asked for: the T&P paragraph holding the 2025-26 placement figures ranks 293rd corpus-wide but 1st inside its own page;
   - `lookup_table(keywords, programme?, gender?, category?, study_year?, academic_year?)` — rows of the documents' tables from `data/processed/facts.db` (`build_facts.py`: 31,682 cells), one result per table row, filtered by tags read from the document title, with SQL built in code and parameterised. Offered unless `LOOKUP_TABLE=off`; in the live runs so far the agent has not chosen it (EXPERIMENTS-LOG §25);
   - `calculate(expression)` — exact arithmetic (an AST walker, never `eval`), so totals are not done "in the head".
   Up to 2 rounds, at most 2 tool calls per round. A tool that fails returns an error message the model can correct, never an exception.
4. **Answer** with citations `[P3]`. The final answer is written from a clean prompt holding every passage found (no tool history): with the tool calls still in the conversation, gpt-oss kept calling tools even when none were offered, and Groq rejected the reply (`400 tool_use_failed`).
5. **Verify** (`verifier.py`, plain code, no LLM): every figure ≥ 10, date, email and phone number in the answer must appear in a passage the model was shown, be a `calculate` result, or be the visible result of arithmetic written in the answer ("1,25,000 × 4 = 5,00,000", whose arithmetic is checked). Number formats are normalised (Indian grouping, lakh ↔ digits, phone numbers split differently, "19 th" → "19th"). It cannot judge names or whether a figure is attached to the right label — it checks what can be checked exactly, which is also where a wrong answer does most harm (fees, deadlines).
6. **Revise.** If anything is unsupported, the model is told which figures and gets one rewrite; the rewrite is verified again. If it still fails, the answer ends with "Note: I could not confirm X…", and the chat page shows a warning badge.
7. **Cite.** `[P3]` labels become `[1]`, `[2]` numbered by the sources list, which holds only the pages actually cited. Citations to passages never shown are removed and recorded. A refusal lists no sources.
8. **Hand off** (`respond.hand_off`). If the answer is a refusal or still unconfirmed, and the topic has a known office in `data/contacts.json` (hostel, fees, calendar, people, other; copied by hand from the Contact Us and Administrative Officers pages), the answer ends with "**Who can help:** office — email, phone" and that page is added to the sources. Topics whose office no page names get nothing rather than a guess.

Every step is returned as `trace` and shown under each answer as **"How I found this"**; `verification` drives the badge ("✓ 4 figures checked against sources" / "⚠ not confirmed: …"); `usage` records LLM calls, tokens, tool calls and time spent waiting for quota.

**Budget.** Groq's free tier allows 8,000 tokens a minute *per model*, and counts the requested `max_tokens` up front. One agent call is ~3,000 prompt tokens. So: `max_tokens` is 1,200 (at 2,000 a tool round's second call was always refused); tool results are 3 passages; a passage already shown is referred to by label only; the agent stops acting when its prompt would exceed 6,000 tokens; and a process-wide pacer reads Groq's `x-ratelimit-remaining-tokens` header and waits the few seconds the refill needs instead of running into a 429. A question that uses tools typically costs ~10,000 tokens and 30–70 seconds on the free tier; one answered from the first search costs ~3,000 tokens and a few seconds.

**Two models, two allowances.** The free tier also caps each model at roughly 200,000 tokens per rolling 24 hours. A full 39-question check through the agent needs ~230,000. So the agent runs on `openai/gpt-oss-120b` (`AGENT_MODEL`), the larger model of the same family, which is also better at choosing tools; the one-shot fallback and the follow-up rewrite stay on `openai/gpt-oss-20b` (`GENAI_MODEL`). When one model's daily allowance is spent, the other still answers. The daily limit is recognised from Groq's error text and stops the agent at once, rather than waiting and retrying.

**Fallback.** If the agent cannot run (no key, quota spent, network), `respond.py` writes the answer in one step from the same first search (`generate.llm_answer`), which itself falls back to quoting passages — and the one-shot answer is still verified, since the check needs no LLM. `AGENT_MODE=off` forces the one-shot path.

---

### 5b. Agent v2 (branch `agent-v2`, Runbook 11, REPORT11.md)

Every v2 behaviour is behind `AGENT_V2` (on in this branch); `AGENT_V2=off` gives v1's exact behaviour on the same code, which the tests check (v1's 73 tests pass unchanged with it off).

**Memory (`memory.py`).** The page sends `turns: [{q, a}]`. The server keeps the last 6, each answer cut to 600 characters without its citation numbers and footers, the block within ~1,500 tokens (oldest dropped first), and stores nothing. The follow-up rewrite (`followup.py`) sees the answers too, and item references ("the second one") count as follow-ups. The agent's first message carries a "Conversation so far" block labelled as context; the verifier never sees it, so a figure from an earlier answer must be found again.

**The loop (`agent_loop.py`).** It reuses planner.py's client, pacer, `Evidence`, final prompt, citations and verifier step, and differs in the loop only:

| | v1 (`planner.run`) | v2 (`agent_loop.run`) |
|---|---|---|
| Rounds of tools | 2 | up to `AGENT_V2_MAX_STEPS` (6) |
| Calls per round | 2, one after another | up to 3, run in parallel |
| Plan | none | 1-4 parts written first, shown in the trace, tracked (by the model's "Done: 1, 3" or by code) |
| Stops when | answered, or 2 rounds | answered; every plan part done; the next round would pass `AGENT_V2_BUDGET` (14,000 tokens); two rounds with nothing new |
| After each round | nothing | one line written by code: what the round found and what to try next, steps and tokens left |
| Long conversations | stop searching | compact: keep cited and newest passages, list the titles set aside |
| Repeated identical call | run again | skipped, with a note |
| Answer | not streamed | streamed (`emit`), `[P3]` → `[1]` on the fly; Stop (`cancel`) at the next step or token |

**Tools (`tools.py`, offered only to v2).** `latest_notices(category, n)` (inventory + status, converted and kept, newest first); `fetch_vnit_page(url)` (only `vnit.ac.in` and sub-sites, compared as a whole host; robots.txt, 1 request a second, 10 s, 2,500 characters, 24-hour cache in `data/cache/pages/`, the crawled copy when offline; `LIVE_PAGES=off` removes it); `today()` (IST, as a passage); `contact_office(topic)` (`data/contacts.json`). All results become `[P#]` passages the verifier checks.

**Task types (`router.task`).** `lookup`, `compare` (a markdown table, one row per item, every cell cited), `summarise` (find the document, read it in order, 5-8 cited bullets), `explain` (numbered steps from passages, then the office), `draft` (written freely with placeholders; every VNIT fact cited; the office email from `contact_office`; "Draft — check before sending." added by code), `general` (only a short concept question with nothing VNIT-specific or time-sensitive in it: one LLM call, no search, labelled "General answer, not from VNIT's documents", verified against no passages so any figure is flagged), `chat` (fixed replies; "what can you do?" lists v2's abilities). The 10 must-decline cases are never `general` (tested).

**Languages (`language.py`).** Devanagari → Hindi or Marathi (common words of each), Latin-script Hindi → Hinglish (kitni, kya, hai…). The first search runs on English keywords made in code (a small glossary plus anything already in Latin letters or digits); the agent is told to search in English and answer in the student's language with figures exactly as in the sources; Devanagari digits are turned into 0-9 before verifying.

**Streaming (`api/main.py`).** `POST /ask/stream`, same body and limits as `/ask`, returns Server-Sent Events: `step`, `token`, `replace`, `done` (exactly `/ask`'s JSON, tested), `error`. The answer runs in a worker thread; a `: ping` comment every 10 s of silence; a disconnect sets the cancel flag. `done` carries `suggestions` (2-3, in code, from cases known to be answered right), `task` and `language`.

**Chat page (`frontend/index.html`) and widget (`vnit-website`, branch `agent-v2`).** Stream reader with live steps, Stop, Copy, Regenerate, Edit (last question), suggestion chips, New chat, empty state, tables; `/ask` as the fallback; state in memory only (optional per-tab `sessionStorage`, off by default).

**Fake LLM (`fake_llm.py`).** `AGENT_FAKE_LLM=on` makes a pretend model answer from the passages, for showing and screenshotting the page without spending allowance; its answers say "agent v2 (fake-llm)".

## 6. Measured quality

Run on 2026-10-03 with 81 pages + 406 documents (8,162 chunks). Full answers: `data/processed/answer_check.json`.

> **Latest (2026-10-30), with the agent:** **35/39** on the 39-case check (34 facts, 5 that must be declined, 2 two-turn conversations), every question reaching the LLM, all 5 must-decline questions refused; the agent used tools on 9 of the 39. The four failures are the documented weak spots (placements, M.Sc and B.Arch tuition, slot-A mid-sem). Details, the baseline comparison and what the agent changed are in EXPERIMENTS-LOG.md §20. The tables below are the 18-question rounds of September and October, kept as the history of how retrieval got here.

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
- Personal-data filtering is heuristic: titles, plus the density of roll numbers, student emails and, since 2026-11-20, "Name of the candidate/student/applicant" labels. 34 documents excluded, and every converted document re-checked against it, but it's not a guarantee.
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
| `AGENT_TOOLS` | `on` | `off` offers the agent no tools: it answers from the first search (for the ablations, EXPERIMENTS-LOG §26) |
| `VERIFY_REVISE` | `on` | `off` still verifies and flags, but makes no revision call (ablations) |
| `AGENT_MODE` | `on` | `off` answers every lookup with the one-shot pipeline instead of the agent |
| `LOOKUP_TABLE` | `on` | `off` removes the `lookup_table` tool (it is also removed if `facts.db` has not been built) |
| `CLARIFY` | `on` | `off` disables clarifying questions (§5a step A) |
| `CRAG_GATE` | `on` | `off` disables the corrective retrieval gate (§5a step B) |
| `AGENT_MODEL` | `openai/gpt-oss-120b` | The agent's model. Kept different from `GENAI_MODEL` on purpose: Groq's free daily allowance (~200,000 tokens) is per model, so when the agent's runs out, the one-shot fallback still has its own |
| `GENAI_TOKENS_PER_MINUTE` | `8000` | The provider's per-minute token allowance, used by the agent's pacer until the first response's headers report the real figure |
| `AGENT_V2` | `on` (branch `agent-v2`) | `off` gives v1's exact behaviour: `planner.run`, questions-only history, no task types, languages, suggestions or new tools (§5b) |
| `AGENT_V2_MAX_STEPS` | `6` | Most rounds of tools v2 may take for one question |
| `AGENT_V2_BUDGET` | `14000` | Tokens one question's tool rounds may spend (the final answer and a revision come after it) |
| `LIVE_PAGES` | `on` | `off` removes the `fetch_vnit_page` tool (no live vnit.ac.in pages) |
| `AGENT_FAKE_LLM` | `off` | `on` answers with a pretend model (`fake_llm.py`) for demos and screenshots without Groq |
