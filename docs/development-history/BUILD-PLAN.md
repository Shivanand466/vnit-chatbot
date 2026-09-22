# BUILD-PLAN.md — from here to a finished, usable application

**Audience: Claude Code (or any developer) working on Shivanand's machine.**
**Companion file: `APPLICATION.md`** — that one describes what exists and how it works. This one describes **what is left, exactly how to do it, and what to do when something breaks.**

Read `APPLICATION.md` first (10 minutes), then this file, then start at whichever Step below is not yet marked done.

---

# PART A — How this project got here (the conversation so far)

This section exists so you don't re-litigate decisions that were already made for reasons, or re-run experiments that already failed. Every claim here was verified on real hardware and is recorded in the `REPORT*.md` files.

## A1. What Shivanand asked for

He brought a presentation (`Agentic AI College Rulebook Assistant.pptx`) about a chatbot answering questions from a college rulebook, and asked for a plan based on it — explicitly saying the plan did *not* have to follow the presentation's approach. Then: **"you are going to do that project for me!"**

Three scope decisions were settled up front:
1. **Coverage: the whole VNIT website**, not just rulebooks. Any question a student might ask about `vnit.ac.in`.
2. **Budget: zero.** Free and open-source only. No paid API, no paid vector database, no paid hosting.
3. **He directs, Claude builds.** Phase by phase, on his command. He has said repeatedly to keep going without pausing — but he has *also* asked for honesty over optimism, which has mattered: several rounds found that a "fix" made things worse, and saying so plainly is what kept the project on track.

He has also said, in his own words, that he is **a beginner at building applications**. Instructions aimed at him should assume no prior deployment/ops knowledge. Instructions aimed at you (Claude Code) can be technical.

## A2. The two-machine constraint that shapes everything

Cowork (the Claude session doing design and coding) runs in a **cloud sandbox with a restricted egress proxy**. Confirmed blocked from it, repeatedly: `vnit.ac.in`, `huggingface.co`, `api.groq.com`, `openrouter.ai`, `api.together.xyz`, `generativelanguage.googleapis.com`, `api.openai.com`. Confirmed *reachable* from it: PyPI, GitHub release downloads.

**Shivanand's machine (where you run) has normal, working internet.** This was proven repeatedly — it reaches `vnit.ac.in`, Groq's API, and (as of Round 5) `huggingface.co` fine.

So the working pattern is: **Cowork writes and locally tests the code → hands you a `RUNBOOK-N-*.md` → you execute it against the real world and write `REPORT-N.md` → Cowork reads it back and fixes whatever it revealed.** Six rounds of this have happened. It works, and it is why every number in these documents is a measured number rather than an assumption.

## A3. What each round found (condensed)

| Round | What was done | What it found |
|---|---|---|
| 1 | First end-to-end test of the 19-page pilot | LLM answers, frontend, real internet all work. **Bug found:** Groq had retired the hardcoded model `llama-3.1-8b-instant`. Fixed → `openai/gpt-oss-20b`. |
| 2 | Real crawl, expanding 19 → **79 pages** | **Chunking bug:** the chunker split on blank lines, which real scraped HTML doesn't have — 79 pages were collapsing into just 82 chunks. Also: Groq 429s from oversized chunks; crawler wasting requests downloading PDFs it then discarded; duplicate-URL crawling. |
| 3 | Verify Round 2's fixes | All confirmed (417 chunks, 95% benchmark, 6/6 LLM calls, zero 429s). **Two new bugs:** the API's `sources` field named pages the LLM never saw; correct pages sat at rank 3 but only the top 2 were ever sent to the LLM. |
| 4 | Verify Round 3's fixes | Both confirmed fixed. **Precisely diagnosed the remaining gap:** answers existed on correctly-retrieved pages but in chunks ranked 4th–12th, below what reached the LLM. Chunk-level ranking, not page-level. |
| 5 | **Real sentence embeddings** | Worked. `all-MiniLM-L6-v2`, 417 chunks, ~46s. **Two of three hard questions fixed outright** (Civil intake = 120/year; 5G lab announced 27 Oct 2023) — both jumped from rank 4–12 to **rank 1**. Benchmark went 95% → 89%, and keeping embeddings anyway was a deliberate, reasoned call (see A5). **Security finding:** the key "rotation" hadn't revoked the old key. |
| 6 | *In flight* — see Step 1 below | Awaiting `REPORT6.md`. |

## A4. Experiments that were tried and REJECTED (do not redo these)

Full detail with numbers in `EXPERIMENTS-LOG.md`. Summary:

- **Date-boost heuristic for "when" questions** — boost any chunk containing a year. Fixed the 5G date case, **broke** the CSE-establishment case (hijacked by an unrelated page that also mentioned a date). Benchmark 18/19 → 17/19. **Rejected.**
- **Static word-vector embeddings** (spaCy `en_core_web_md`, as a lighter alternative to a transformer). Plain averaging: **4/19**. TF-IDF-weighted averaging: **13/19**. Both far worse than TF-IDF's 18/19. Mean-pooled static vectors are a known-weak sentence representation, and this site is full of proper nouns they represent poorly. **Rejected — this is not a viable "cheap embeddings" middle ground.**
- **Smaller chunk sizes** (100 / 80 / 60 words vs the current 150). All scored worse: 16/19, 17/19, 15/19. **Rejected — 150 stays.**

## A5. Standing decisions (don't reverse these without new evidence)

- **Embeddings stay the default**, even though the page-level benchmark prefers TF-IDF (89% vs 95%). The benchmark only asks "is the right *page* in the top 3." Embeddings measurably fixed the chunk-level failures that were producing actually-wrong answers for users. TF-IDF remains the automatic fallback if embeddings can't be built.
- **`mode` is always reported** in the API response and shown in the UI. A user must always be able to tell whether an answer came from the LLM or the extractive fallback.
- **The LLM is instructed to say "not covered in these passages" rather than guess** — and across five rounds of real testing, **zero hallucinations were observed.** This behaviour is a feature of the project, not an accident. Do not "improve" the prompt in a way that pressures the model to always produce an answer.
- **`CHUNK_WORDS = 150`, `OVERLAP_WORDS = 30`** — empirically chosen, see A4.
- **Never delete or overwrite `REPORT*.md` files.** They are the project's evidence trail.

---

# PART B — The final outcome we are aiming at

**Definition of done.** The project is finished when all of the following are true and demonstrated:

1. **It answers real questions about the VNIT website correctly, with citations.** A student can ask about admissions, fees, hostels, placements, any department, contacts, or anything in a linked PDF notice, and get a correct answer with a working source link.
2. **Coverage includes PDFs**, not just HTML pages — because fee schedules, notices and handbooks on this site are frequently PDFs.
3. **It never invents answers.** When the corpus doesn't cover something, it says so. (Already true — must stay true.)
4. **It runs end to end from a clean checkout** with a documented sequence of commands, on Shivanand's machine, without hidden manual steps.
5. **Accuracy is measured, not claimed** — `evaluate.py` produces a number, and that number is recorded honestly along with known failure cases.
6. **It is demonstrable for the FYP**: a working chat UI he can open and use live in front of evaluators, without depending on anything fragile.
7. **No security loose ends** — no live API key that has ever been pasted into a chat.
8. **The documentation matches reality** — `APPLICATION.md` status section reflects what is actually true on the day the project is submitted.

**Explicitly NOT required for "done"** (nice-to-have, judge by remaining time):
- Public internet deployment. **For an FYP demo, running locally on his laptop is completely legitimate** and removes an entire category of risk. Deployment is Step 3 and is optional.
- A React frontend. The existing plain HTML/JS UI is confirmed working; rewriting it adds risk and no marks.
- OCR for scanned PDFs.

---

# PART C — The steps, in order

Work through these in order. Each step states its goal, the exact commands, what success looks like, **what to do if it fails**, and what to record.

## Global rules for every step

- **Run every step even if an earlier one had problems** — a documented failure is more useful than a skipped step.
- **Record the numbers you actually saw**, never the numbers this document predicts. If they differ, that difference is the most valuable thing in your report.
- **If a command fails, consult PART D (Troubleshooting) before improvising.** Most failure modes here have already been hit once and have a known alternate path.
- **If you must deviate from these instructions, say so explicitly in your report** and explain why — don't silently substitute an approach.
- **Never commit or paste an API key** into any file, report, or commit message.
- After each step that changes code or data, re-run `python3 evaluate.py` as a regression check.

---

## STEP 1 — Finish the open verification round (RUNBOOK-6)

**Status: in flight.** If `REPORT6.md` already exists in this folder, this step is done — skip to Step 2.

**Goal:** confirm two things from the previous round: (a) a code fix for the last failing question actually works, (b) the old Groq API key is actually revoked.

Follow `RUNBOOK-6-PLACEMENTS-FIX-AND-KEY-CLEANUP.md` exactly and write `REPORT6.md`. Short version of what it covers:

```bash
cd vnit-chatbot
export GENAI_API_KEY="<current key>"
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "How many students got placed in 2025-26 and how many companies came?"}' | python3 -m json.tool
kill %1
```

**Success looks like:** the answer contains the real placement numbers (the corpus says "more than 678 students… over 170 reputed organizations") cited to the TNP page, and `mode` is `llm (openai/gpt-oss-20b)`.

**If it still says "not found":**
1. First check *which index is loaded* — this is the most likely cause:
   ```bash
   cd pipeline && python3 -c "import pickle,pathlib; d=pickle.load(open(pathlib.Path('../data/processed/index.pkl'),'rb')); print('index type:', d.get('type','tfidf'), '| chunks:', len(d['chunks']))"
   ```
   It must print `embeddings`. If it prints `tfidf`, the fix cannot work — rebuild with `python3 build_index.py` and confirm the `[embeddings]` lines appear, then retry.
2. If it *is* the embeddings index and it still fails, measure where the answer chunk actually ranks:
   ```bash
   cd pipeline && python3 -c "
   from query import retrieve
   for i,r in enumerate(retrieve('How many students got placed in 2025-26 and how many companies came?', k=15),1):
       print(i, round(r['score'],3), r['source_url'][:70])
   "
   ```
   Report the rank of the `section/tnp/` chunk. If it is outside the top 3, the merge fix is working but `k` is too small — try `agent.answer(question, k=5)` and report whether that fixes it.

**The key revocation (Step 1 of that runbook) requires Shivanand, not you** — deleting a key is a browser action in console.groq.com. Your job is only to verify it took effect: `curl -sS https://api.groq.com/openai/v1/models -H "Authorization: Bearer <old key>"` must return 401/403, not 200. If it still returns 200, say so plainly in the report — this has already been missed twice.

---

## STEP 2 — Ingest PDFs (the last real coverage gap)

**Goal:** get the text of linked PDFs (notices, fee schedules, handbooks) into the corpus, so questions whose answers live only in a PDF can be answered.

**The code is already written and tested: `pipeline/ingest_pdfs.py`.** Its extraction, cleaning, title-derivation and downstream integration were all tested in Cowork's sandbox against a real generated PDF (confirmed: extracted correctly with both engines, TOC dot-leaders and bare page numbers stripped, real content preserved, the resulting file chunked and indexed and came back as the top hit for a question about its contents). **What could not be tested there is the network half** — discovering and downloading real PDFs from `vnit.ac.in`. That's this step.

### 2.1 Install a PDF engine

```bash
pip install pdfplumber
```

`ingest_pdfs.py` tries **pdfplumber** first (better reading order on multi-column layouts) and falls back to **pypdf** automatically, per PDF, if pdfplumber isn't installed or chokes on a specific file.

**If `pdfplumber` fails to install** (it pulls `pdfminer.six` and `pillow`, which occasionally have build trouble on Windows):
```bash
pip install pypdf
```
pypdf is pure Python with no binary dependencies and installs essentially everywhere. The module will use it automatically. Extraction quality is slightly lower on complex layouts, which is an acceptable trade — note in your report which engine ended up being used (the script prints it per file).

**If neither installs**, stop and report it. Do not attempt to write a PDF parser by hand.

### 2.2 Dry run first — look before you download

```bash
cd pipeline
python3 ingest_pdfs.py --dry-run
```

This crawls the site's HTML collecting PDF links but **downloads nothing**. Record: how many PDF links were found, and eyeball whether they look like useful content (notices, fee structures, calendars) versus junk.

**If it finds 0 PDFs:** that contradicts Round 2's finding of ~39 unique PDFs across just 12 sampled pages, so something is wrong. Check in this order: (a) is `vnit.ac.in` reachable right now (`curl -sSI https://vnit.ac.in | head -1`), (b) raise the crawl breadth (`--max-html-pages 150 --max-depth 4`), (c) confirm `extract_pdf_links` is matching by testing one known page manually. Report which.

### 2.3 Real ingestion

```bash
python3 ingest_pdfs.py --max-pdfs 40 --max-html-pages 80 --max-depth 3
```

It is rate-limited to ~1 request/second by design (politeness to the institute's server), so 40 PDFs plus the HTML crawl will take several minutes. That is expected, not a hang.

**Record:** how many were ingested, how many were skipped as scanned/image-only (these need OCR, which is out of scope — but the count tells us how much is being left behind), how many errored and why.

**Known failure modes and what to do:**
- **Many/most skipped as "likely a scan"** → the site's PDFs are image scans. This is a real finding, not a bug. Report the proportion. Do not add OCR without asking — `pytesseract` needs a system-level Tesseract binary install, which is a significant dependency for a beginner-maintained project.
- **`PermissionError: robots.txt disallows`** → correct behaviour, leave it. Do not bypass robots.txt.
- **Timeouts / connection resets on a few files** → normal for a large site. They're caught and logged per-file; the run continues. Only investigate if *most* files fail.
- **Encrypted PDF errors** → caught and logged, expected, move on.
- **The run takes too long** → lower `--max-pdfs`. Ingesting 20 good PDFs is a fine outcome for this step.

### 2.4 Rebuild and re-measure

```bash
python3 chunk.py
python3 build_index.py
python3 evaluate.py
```

**Expected:** chunk count rises meaningfully above 417 (proportional to PDFs ingested). Benchmark should stay **roughly** where it was (89% with embeddings).

**If the benchmark drops by more than ~1 question:** the PDF text is probably adding noise that outranks real content. Diagnose before reverting:
```bash
python3 -c "
from query import retrieve
for r in retrieve('<one of the now-failing benchmark questions>', k=5):
    print(round(r['score'],3), r['source_url'][:80])
"
```
If PDF chunks are crowding out HTML pages, the most likely culprit is boilerplate-heavy PDFs (letterheads, repeated headers). Two options in order of preference: (a) raise `MIN_WORDS` in `ingest_pdfs.py` to exclude thin PDFs, re-run; (b) if that doesn't help, move the PDF files out of `data/raw/` into `data/raw_pdfs_quarantine/`, rebuild, and report that PDFs need better cleaning before inclusion. **Reverting cleanly and reporting why is a perfectly good outcome** — do not force a worse system through.

### 2.5 Prove it actually helps

Pick 2–3 questions whose answers you can see are *only* in a newly-ingested PDF (open one of the new `data/raw/pdf_*.txt` files and read it). Ask them through the API and confirm the PDF is cited.

```bash
export GENAI_API_KEY="<current key>"
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "<your PDF-specific question>"}' | python3 -m json.tool
kill %1
```

**Record all of the above in `REPORT7.md`.**

---

## STEP 3 — Decide and set up how it will be demonstrated

**This step needs Shivanand's decision first.** Ask him which he wants; don't assume.

### Option A (recommended, zero risk): run locally for the demo

Nothing to build. Write him a one-page `HOW-TO-DEMO.md` containing the exact startup sequence, a list of 6–8 questions known to answer well, and what to do if something misbehaves mid-demo. Keep it short enough to follow while nervous.

```bash
cd vnit-chatbot
export GENAI_API_KEY="<key>"          # Windows PowerShell: $env:GENAI_API_KEY="<key>"
uvicorn api.main:app --host 0.0.0.0 --port 8000
# then open frontend/index.html in a browser
```

**A genuine caveat to write into that file:** the LLM answer path needs internet (Groq's API). If the venue's wifi fails, the app falls back to extractive mode automatically and still works — it just produces passage-stitched answers instead of composed ones, and the UI will show `mode: extractive (...)`. **Tell him this in advance** so it's a known degradation rather than a surprise. Optionally rehearse it once with wifi off so he's seen it.

### Option B: deploy it publicly

`Dockerfile` has already been rewritten for this and includes the two things that otherwise break it: **CPU-only PyTorch** (the default wheel bundles ~2.5GB of unused CUDA libraries) and **pre-downloading the model at build time** (otherwise the first user question triggers a huggingface download inside the container).

```bash
docker build -t vnit-chatbot .
docker run -p 8000:8000 -e GENAI_API_KEY=xxx vnit-chatbot
curl -sS localhost:8000/health
```

**Before picking a host, know the memory constraint:** PyTorch + MiniLM needs roughly 400–600MB of RAM resident. **Render's free tier (512MB) is likely too tight** — expect OOM kills. Better free options, in order:
1. **Hugging Face Spaces** (Docker SDK, free CPU tier with ~16GB RAM) — by far the most comfortable fit for this workload, and it's where the model comes from anyway.
2. **Fly.io / Railway** free allowances — workable, check current RAM limits.
3. Any VM with ≥1GB RAM.

**If RAM is the binding constraint and you must fit a small box**, the knowledge-based alternate is to drop PyTorch entirely and use ONNX at query time: `pip install fastembed` ships an ONNX build of the same MiniLM family at a fraction of the footprint (~50MB, no torch). That would require a small change in `query.py`'s `_get_embedding_model` to use fastembed's encoder, and **the index would need rebuilding with the same model** so vectors are comparable. **Do not attempt this unless RAM actually forces it** — it's a real option, not a default, and it must be followed by re-running `evaluate.py` to confirm accuracy held.

**Two things to fix before any public deployment** (they're fine for local use, not for the open internet):
1. **CORS is wide open** in `api/main.py` (`allow_origins=["*"]`). Narrow it to the actual frontend origin.
2. **There is no rate limiting.** A public endpoint with your Groq key behind it can be drained by anyone who finds it. Add basic per-IP limiting (`slowapi` is the usual FastAPI choice) or keep the URL private.

---

## STEP 4 — Full clean-run acceptance test

**Goal:** prove the whole thing works from scratch, in order, with nothing cached in your head from earlier steps. This is what makes claim 4 in PART B true.

```bash
cd vnit-chatbot
pip install -r requirements.txt

cd pipeline
python3 chunk.py         # expect: N chunks from M files
python3 build_index.py   # expect: [embeddings] lines, NOT [fallback]
python3 evaluate.py      # expect: a hit-rate; record it

export GENAI_API_KEY="<key>"
cd ..
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -sS localhost:8000/health
```

Then run **at least 10 questions** through `POST /ask` spanning: admissions, fees, hostels, placements, at least three different departments, a contact/phone question, a "when was X established" question, one compound question with "and", one question you know the corpus *cannot* answer, and one whose answer is in a PDF.

**For each, record:** the question, `mode`, `sources`, and whether the answer is actually correct (check it against `data/raw/`, don't just eyeball plausibility).

**The question you know it can't answer is the most important one in the set.** It must say it doesn't know. If it invents an answer instead, that is a serious regression — stop, report it immediately, and do not proceed to Step 5.

Write this up as `REPORT8.md` — it doubles as the evidence table for his FYP report.

---

## STEP 5 — Make the documentation true, then stop

1. Update `APPLICATION.md` **section 2** (status table) and **section 12** (next steps) to match reality as of that day. Stale status is worse than no status.
2. Update `README.md`'s headline numbers if they changed.
3. Confirm no API key appears anywhere in the repo: `grep -ri "gsk_" . --include="*.md" --include="*.py"` should return nothing.
4. Write a short `FINAL-STATUS.md`: what works, the measured accuracy number, the known limitations (in plain language — e.g. "scanned PDF notices aren't readable", "placement statistics questions are unreliable if X"), and what a future team would do next.

**Then stop.** Resist adding features at this point. A finished, honest, working project beats a half-finished ambitious one, and the limitations list is worth marks precisely because it shows the system was actually evaluated.

---

# PART D — Troubleshooting: every failure mode this project has actually hit

Consult this before improvising. Each of these was encountered for real, or is a known property of the libraries involved.

### LLM / Groq

| Symptom | Cause & fix |
|---|---|
| `mode` says `extractive (no GENAI_API_KEY set)` | The env var isn't in *this* shell. Re-export it. Each new terminal needs it again. PowerShell uses `$env:GENAI_API_KEY="..."`, not `export`. |
| `model_not_found` / 404 from Groq | **This already happened once** — Groq retired `llama-3.1-8b-instant` mid-project. Providers rotate models. Fix: `curl -sS $GENAI_BASE_URL/models -H "Authorization: Bearer $GENAI_API_KEY"` to list current models, then set `GENAI_MODEL` to a live one. Don't assume the code is broken. |
| `429 Too Many Requests` | Free-tier token/minute cap. Already mitigated (`MAX_CHUNK_CHARS=700`, `MAX_CONTEXT_CHARS=6000` in `generate.py`) and Round 5 saw zero 429s. If they return: lower `MAX_CONTEXT_CHARS`, or space out requests. Do **not** raise the caps to "get more context." |
| 401/403 from Groq | Key revoked, expired, or wrong. Expected for the *old* key after Step 1 — that's success, not an error. |
| Answers are wrong but confident | Stop and report immediately. Zero hallucinations have been observed in five rounds; a change in that is the highest-severity finding possible here. |

### Retrieval / index

| Symptom | Cause & fix |
|---|---|
| `build_index.py` prints `[fallback]` | Embeddings couldn't be built. Read the printed reason. `not installed` → `pip install sentence-transformers`. Network/proxy error → check `curl -sSI https://huggingface.co`. The app still works on TF-IDF meanwhile — this is a degradation, not an outage. |
| Benchmark suddenly much lower | Something changed the corpus or chunking. Check chunk count first (`python3 chunk.py` prints it). A large jump or drop points at `data/raw/` changing. |
| `FileNotFoundError: index.pkl` | Run `python3 chunk.py` then `python3 build_index.py`, in that order, from inside `pipeline/`. |
| `ModuleNotFoundError` for `query`/`agent` | You're not in `pipeline/`, or running the API from the wrong directory. The API inserts `pipeline/` into `sys.path` itself — run it as `uvicorn api.main:app` **from the project root**, not from inside `api/`. |
| Unpickling error on `index.pkl` | Version skew (index built with a different scikit-learn/numpy than the one loading it). Just rebuild: `python3 build_index.py`. Never hand-edit the pickle. |

### Crawling

| Symptom | Cause & fix |
|---|---|
| Crawl returns almost nothing | Check `curl -sSI https://vnit.ac.in | head -1` first — the site may be down or slow. Then check whether `SKIP_PATH_PATTERNS` is over-matching. |
| Everything shows `[CHANGED]` on first recrawl | **Expected once.** The original 19 pages were fetched through a paraphrasing tool; the first real re-crawl replaces them with verbatim text. Documented in `recrawl.py`'s docstring. Not 19 real edits. |
| Pages come back full of nav junk | The site's theme doesn't use semantic `<main>`/`<article>` tags, so extraction falls back to `<body>`. Known limitation. If it materially hurts a page, a targeted CSS-selector rule for that template is the fix — but measure before and after with `evaluate.py`. |
| robots.txt blocks something | Respect it. Do not add a bypass. This is a student project crawling their own institute's public site — politeness is non-negotiable. |

### Environment (Windows / Anaconda specifically — that's the actual setup)

| Symptom | Cause & fix |
|---|---|
| `pip install` changes other package versions | Round 5 saw `sentence-transformers` upgrade `click` and `setuptools` in the shared Anaconda env. Nothing broke, but a `python -m venv .venv` would isolate this. Worth doing if anything starts behaving oddly. |
| HF symlink warning on Windows | Harmless. The model cache works, just uses more disk. Ignore, or enable Developer Mode. |
| `Address already in use` on port 8000 | An old uvicorn is still running. Find and kill it by *port*, not by matching "uvicorn" in the process list — a pattern match can match the killing command itself (this bit Cowork once). `lsof -ti:8000 | xargs -r kill -9`, or on Windows `netstat -ano | findstr :8000` then `taskkill /PID <pid> /F`. |
| Frontend can't reach the API | Check the API URL box on the page, confirm uvicorn is running, and confirm CORS is enabled (it is, wide open, by design for local dev). A `file://` console warning about origin is benign — Round 1 confirmed this. |
| Torch download is enormous / times out | Use the CPU-only wheel: `pip install torch --index-url https://download.pytorch.org/whl/cpu`. ~200MB instead of ~2.5GB. The Dockerfile already does this. |

### General principle when you hit something not listed

1. **Reproduce it minimally** — smallest command that shows the failure.
2. **Read the actual error**, not the first plausible guess. Several bugs in this project looked like one thing and were another (the 429s were really a chunking bug; the "blocked" huggingface was really only blocked from *Claude's* tooling).
3. **Check whether a fallback already exists** — `build_index.py` and `generate.py` both degrade gracefully by design, so a failure there may be recoverable automatically.
4. **Prefer the boring fix.** Rebuild the index, re-export the key, re-run from a clean shell.
5. **If you change code to work around it, re-run `evaluate.py`** and report the before/after number. Every "obvious improvement" in this project that skipped that step turned out to be a regression.
6. **If you cannot fix it, write down exactly what you tried and what happened.** That is a successful outcome for a report. Guessing and moving on is not.

---

# PART E — Quick reference

**Full pipeline from scratch:**
```bash
cd vnit-chatbot
pip install -r requirements.txt
cd pipeline
python3 crawl.py --max-pages 60 --max-depth 3     # optional: expand corpus
python3 ingest_pdfs.py --max-pdfs 40              # optional: add PDFs
python3 chunk.py
python3 build_index.py
python3 evaluate.py
cd ..
export GENAI_API_KEY="<key>"
uvicorn api.main:app --host 0.0.0.0 --port 8000
# open frontend/index.html
```

**Files, and which to read when:**
| File | Read it when |
|---|---|
| `APPLICATION.md` | You need to understand how the system works |
| `BUILD-PLAN.md` (this file) | You need to know what to do next |
| `EXPERIMENTS-LOG.md` | You're about to try a retrieval improvement |
| `REPORT*.md` | You want the evidence behind a claim |
| `RUNBOOK*.md` | Rounds 1–6 task instructions (1–5 are closed history; 6 may be open) |

**Reports you will produce:** `REPORT6.md` (Step 1), `REPORT7.md` (Step 2), `REPORT8.md` (Step 4), plus `HOW-TO-DEMO.md` and `FINAL-STATUS.md` (Steps 3 and 5).
