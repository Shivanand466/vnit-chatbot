# VNIT Website Chatbot — Pilot

A working, end-to-end pilot of the agentic RAG chatbot from the project plan: crawl → chunk → index → decompose → retrieve → compose an answer with citations, plus a minimal API and chat UI. Corpus is now the real 79-page crawl (see "Crawl expansion, fixes, and re-verification" below) spanning admissions, fees, hostels, placements, nine departments, and admin/contact info, discovered by following real links from the homepage rather than 19 hand-picked pages.

## What's here

```
data/raw/*.txt        19 pages fetched from vnit.ac.in, each with SOURCE_URL/TITLE/FETCHED headers
pipeline/chunk.py      splits pages into ~150-word retrieval chunks, keeps source metadata
pipeline/build_index.py  builds a TF-IDF retrieval index (scikit-learn, no downloads needed)
pipeline/query.py      single-question retrieval: top-k chunks + citations
pipeline/agent.py      splits compound questions into sub-questions, multi-hop retrieval,
                       recency tiebreak, conflict flagging
pipeline/generate.py   turns retrieved passages into an answer (LLM-pluggable, extractive fallback)
pipeline/evaluate.py   19-question benchmark scoring retrieval accuracy automatically
pipeline/fetch_utils.py  real HTTP fetch (requests + BeautifulSoup) + robots.txt check + link
                       extraction — needs real internet, unusable inside Claude's sandbox
pipeline/crawl.py      bounded BFS crawler to discover and fetch pages beyond the original 19
pipeline/recrawl.py    re-fetches known pages for real, diffs, updates or marks stale
api/main.py            FastAPI service: POST /ask -> answer + sources + mode
frontend/index.html    minimal chat UI (vanilla HTML/JS) that calls the API
requirements.txt, Dockerfile   for running/deploying this outside Claude's sandbox
```

## How to run it

```bash
pip install -r requirements.txt

# build the index (needed once, and again whenever data/raw/ changes)
python3 pipeline/chunk.py
python3 pipeline/build_index.py

# try retrieval directly
python3 pipeline/query.py "When does B.Tech admission through JoSAA start reporting?"
python3 pipeline/agent.py "What is the fee for B.Tech and where can I find the hostel rules?"

# check retrieval accuracy
python3 pipeline/evaluate.py

# run the API
uvicorn api.main:app --host 0.0.0.0 --port 8000
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "What is the fee for B.Tech and where can I find the hostel rules?"}'

# open frontend/index.html in a browser (it talks to localhost:8000 by default —
# edit the API URL field in the page if you're running the API elsewhere)
```

## What's actually been tested, and how

- **Retrieval**: `pipeline/evaluate.py`'s 19-question benchmark now gets **95% (18/19)** top-3 hit-rate against the real 79-page corpus (see "Crawl expansion, fixes, and re-verification" above for how it got there — it was 100% on the original 19 hand-picked pages, dropped to 74% when the corpus went real and noisy, then recovered to 95% via a chunking fix and vectorizer tuning). Worth being honest about the number either way: I wrote both the questions and picked the pages, so they're generously aligned — a real student's phrasing will be messier. Treat this as "the pipeline mechanics work, including under real noisy data," not "this is production-accurate." Re-run this benchmark after any change to chunking, ranking, or the corpus to catch regressions.
- **Query decomposition**: 3 compound questions correctly split into sub-questions with the right page retrieved for each.
- **The API**: ran `uvicorn` locally and hit `/ask` with curl — full request/response cycle works, CORS is on so the HTML frontend can call it.
- **LLM-composed answers**: confirmed working (2026-09-21) via `RUNBOOK-FOR-CLAUDE-CODE.md`, run on Shivanand's own machine with a free Groq key. Three test questions all came back `mode: llm (openai/gpt-oss-20b)` with correctly composed, cited answers — including correctly saying "not covered in these passages" instead of guessing, when asked something the corpus doesn't have (admission document requirements). One real bug found and fixed in the process: the default model name in `generate.py` had been retired by Groq since this file was written; the default is now `openai/gpt-oss-20b`. See `REPORT.md` for the full transcript.
- **The frontend**: confirmed working in an actual browser (same test run) — typed a question, got a rendered answer with sources and mode shown underneath, exactly as designed.
- **Real internet + a real crawl fetch**: confirmed from the same machine — `vnit.ac.in` returns 200 with real HTML outside Claude's sandbox, so `pipeline/recrawl.py`'s fetch step is unblocked there.

## Crawl expansion, fixes, and re-verification (2026-09-21)

`RUNBOOK-2-CRAWL-EXPANSION.md` was run for real by Claude Code (see `REPORT2.md`): the original 19 pages were re-fetched verbatim, and a real BFS crawl from the homepage found 60 more, for a **79-page corpus**. That run also surfaced real bugs, since real scraped HTML looks nothing like the hand-picked, WebFetch-paraphrased text the pilot was first tuned on. All of the below were found in `REPORT2.md` and fixed and re-verified against the real 79-page corpus in this sandbox (evaluate.py, query.py, agent.py, and the API all re-run against it):

- **Chunking bug (highest priority).** `chunk.py` split paragraphs on blank lines only, which real scraped text (single `\n` between elements, not blank lines) mostly doesn't have — so most pages collapsed into one oversized chunk each (82 chunks total from 79 pages). Fixed: split on any run of newlines, plus a hard word-window fallback so no single chunk can exceed the target size regardless of the source page's layout. Rebuilding against the real corpus now gives 417 appropriately-sized chunks.
- **Retrieval accuracy regression.** With the chunking fix alone, the 19-question benchmark landed at 74% (down from the original 100%, which was measured against clean 19-page pilot data) — real pages are noisy (repeated news blurbs, long notice lists) in ways that strain plain TF-IDF. Tuning the vectorizer (`min_df=2`, `sublinear_tf=True` — drop single-chunk rare terms, dampen repeated-phrase inflation) recovered this to **95% (18/19)** without touching the questions or the corpus. The one remaining miss (Training & Placement stats) is a genuinely hard case — see "Still not built" below on why real embeddings are the more durable fix, not further vectorizer tuning.
- **Groq rate-limit (429) risk.** Oversized chunks (from the chunking bug) could push a single request's context past Groq's free-tier tokens/minute cap. Fixed independently of the chunking fix, as a second line of defense: `generate.py` now truncates each chunk's text and caps total prompt context size before calling the LLM.
- **Crawler hygiene.** Added `/index.php/` and `/category/` to `crawl.py`'s skip patterns (near-duplicate URLs pointing at the same content, found in the real crawl). Added `.pdf` to `fetch_utils.py`'s link filter — PDFs were being fully downloaded by the crawler and then silently discarded (non-HTML), wasting requests; they're now skipped at the link stage instead.
- **A stale claim corrected:** `REPORT2.md` states the retired-Groq-model default (`llama-3.1-8b-instant`) is "still unfixed" — checked directly, the live file already has the `openai/gpt-oss-20b` fix from the previous round; this looks like Claude Code repeating an earlier finding without re-checking, not a real regression.
- **Still open, not touched this round:** the Training & Placement retrieval miss above; PDF *ingestion* (crawler now skips PDFs cleanly, but nothing extracts their text yet); `agent.py`'s query decomposition can still lose subject context on short sub-questions (e.g. "when was it announced"); the Groq API key used for testing has been reused across two test rounds and still needs rotation (see Security note below).

`RUNBOOK-3-FIXES-VERIFICATION.md` asked Claude Code to re-run the real pipeline against these fixes and re-check the previously-failing spot-check questions with an actual LLM call — see `REPORT3.md`. Result: the chunking/vectorizer/rate-limit numbers reproduced exactly (417 chunks, 11187 vocab, 18/19 = 95%), and 6/6 real LLM calls succeeded with zero 429s, confirming the context-cap fix works. But it surfaced two new, more precise bugs on top of the known TF-IDF ranking limits:

- **`sources` field mismatch.** The API was reporting `sources` from only the top-1 retrieved chunk per sub-question, regardless of which chunks were actually sent to the LLM (top-2 at the time) — so it could name a page the model never saw. REPORT3.md caught this concretely: asked about Electrical Engineering's M.Tech, `sources` named the *civil* department page.
- **Right page, wrong rank.** REPORT3.md found the Civil-enrollment and Electrical-M.Tech correct pages were retrieved (rank 3 of 3) but never made it into the LLM prompt, because only the top 2 were sent.
- **Decomposition subject loss**, confirmed for real this time: "Tell me about the 5G lab and when was it announced" split into a second sub-question ("when was it announced") that lost "5G lab" entirely, retrieved an unrelated convocation page, and the LLM correctly said it didn't have the announcement date — right behavior (no hallucination) on wrong context.

Fixed all three: `generate.py` now sends up to top-3 chunks per sub-question (same context-size caps still apply) and builds `sources` from the exact chunks included in the prompt; `agent.py`'s decomposition now detects a dangling pronoun ("it"/"this"/"they"/etc.) in a later sub-question and substitutes in the topic from the sub-question before it. `RUNBOOK-4-CONTEXT-AND-DECOMPOSITION-FIXES.md` had Claude Code re-confirm this with real LLM calls — see `REPORT4.md`. Both fixes verified working: `sources` now matches what was actually in the prompt (Civil and Electrical department pages correctly appear), and the 5G sub-question keeps its subject ("when was the 5G lab announced" instead of a dangling "it").

What REPORT4.md also did: it precisely measured *why* the Civil-intake and 5G-announcement-date questions still come back "not found" even with both fixes in place, by checking the answer-bearing chunk's actual rank among all 417. Civil's "intake of 120 students per year" sentence ranks **12th**; the 5G lab's announcement-date sentence ranks **4th and 9th** (of two mentions). Both are on the correct page (page-level retrieval is fine, per the 95% benchmark) but below whatever cutoff sends chunks to the LLM — a chunk-level ranking problem, not a page-level or decomposition one. This is now a precisely diagnosed, not just observed, gap.

**Follow-up (this sandbox, no device round-trip needed): three ways to close that gap were tried and two were rejected based on real measurement, not guesswork** — see `EXPERIMENTS-LOG.md` for full detail:
1. A global score boost for date-like chunks on "when" questions — fixed the 5G case outright, but broke a different, previously-correct question (CSE department's establishment date got hijacked by an unrelated page that happened to mention a date). Net: benchmark regressed to 17/19. **Rejected.**
2. Real semantic embeddings, attempted via spaCy's `en_core_web_md` static word vectors (downloadable from a GitHub release — huggingface.co is confirmed still blocked from both this sandbox and the device). Averaging word vectors per chunk: **4/19**, far worse than TF-IDF. TF-IDF-weighting that average before comparing: **13/19**, better but still clearly worse than TF-IDF's 95%. **Rejected both** — mean-pooled static word vectors are a known-weak sentence representation, and this site's heavy use of proper nouns (department names, specific figures) plays to TF-IDF's strengths, not generic word vectors'.
3. Smaller chunk sizes (already tried the round before) — also made the automated benchmark worse (150 words remains the best setting tried).

**Net result: no code changed this round.** The current TF-IDF configuration is confirmed to be the best of everything tried, including two credible-sounding "obvious next steps" that turned out to make things worse on real measurement. The honest conclusion is that a proper transformer sentence-embedding model (not static word vectors) is the more promising path left, but needs network access to a host this environment can reach — currently only huggingface.co is known to host it, and that's blocked.

## Real embeddings: code written, awaiting a real test (2026-09-21)

Correction to the note above: huggingface.co being blocked from **Claude's own tooling** (this sandbox and the Cowork device-bridge shell) doesn't mean it's blocked from Shivanand's machine generally — every report so far confirms that machine has real, working internet for other hosts (vnit.ac.in, Groq's API); huggingface.co specifically just hadn't been tested from there yet. So `pipeline/build_index.py` now tries a real `sentence-transformers` embeddings index first (model: `all-MiniLM-L6-v2`, small and CPU-friendly), and only falls back to the tuned TF-IDF setup if that fails for any reason (not installed, or the download doesn't go through) — tested end-to-end in this sandbox with the fallback path (confirmed: falls back cleanly, TF-IDF benchmark still 95%, no regressions). `pipeline/query.py` now transparently retrieves from either kind of index. `RUNBOOK-5-REAL-EMBEDDINGS.md` has Claude Code actually try the embeddings path where it has a chance of working — results land in `REPORT5.md`.

## Real embeddings: confirmed working, two of three hard cases fixed (REPORT5.md, 2026-09-21)

Claude Code ran `RUNBOOK-5-REAL-EMBEDDINGS.md` for real: huggingface.co **is** reachable from this machine (confirmed HTTP 200), the embeddings index built successfully (`all-MiniLM-L6-v2`, 417 chunks, ~46 seconds total including model download), and `data/processed/index.pkl` is now a real embeddings index, not TF-IDF.

- **Automated benchmark: 17/19 = 89%**, slightly below TF-IDF's tuned 95%. Not a strict win on that specific metric — it fixed the chronic Training & Placement page-retrieval miss but introduced a new near-miss (Registrar's phone number, a case where exact keyword matching actually helps).
- **But the two known chunk-ranking failures are both fixed for real**, confirmed end-to-end with actual LLM answers: "How many undergraduate students does Civil Engineering enroll annually?" now correctly answers **120 students/year**, correctly cited; "Tell me about the 5G lab and when was it announced" now correctly finds **27 October 2023**, correctly cited. Both answer-bearing chunks jumped from rank 4-12 (TF-IDF) to **rank 1** (embeddings).
- **Verdict: keep the embeddings index.** The benchmark's -1 is a page-level metric on a benchmark written for TF-IDF's strengths; the real gain is in chunk-level precision, which is what was actually producing wrong "not found" answers in practice.
- The third hard case (Training & Placement stats) still failed — but for a newly diagnosed, different reason: decomposition splits the question into two halves that individually can't find the stats chunk, even though it ranks 2nd for the *undivided* question. Fixed this round (see below).
- **Not yet done, flagged in REPORT5.md**: the Groq key rotation was incomplete — a new key was supplied, but the *old* one was never revoked (confirmed still valid). See Security note below. Also: the `Dockerfile` will need updating for deployment, since `sentence-transformers` pulls in PyTorch and makes the image much larger; and a hybrid TF-IDF+embeddings score could plausibly recover the Registrar/Electrical-M.Tech misses, not attempted yet.

**Fixed this round**, following REPORT5.md's own diagnosis directly: `agent.py`'s `answer()` now also retrieves for the *undivided* question whenever it gets decomposed, and `generate.py` merges anything new from that pass into the LLM's context (deduped, same size caps as before). This is a strict superset of the previous behavior — it only adds candidate chunks, never removes ones the sub-questions already found — so it can't cause a regression, and confirmed it doesn't (still 95% on the TF-IDF benchmark, single-question flow unaffected). Whether it actually fixes the placements question needs the real embeddings index already on this machine to confirm — `RUNBOOK-6-PLACEMENTS-FIX-AND-KEY-CLEANUP.md` has Claude Code check that, and also actually finish the key rotation this time.

## Still not built

- **Confirming the placements fix + finishing key rotation** — pending `REPORT6.md`.
- **Deployment packaging for the embeddings model** — `Dockerfile` doesn't yet account for `sentence-transformers`/PyTorch's larger footprint or pre-downloading the model at build time (currently it would download on first request).
- **Hybrid TF-IDF+embeddings scoring** — could plausibly recover the two cases where embeddings alone slipped (Registrar's phone number, Electrical M.Tech specializations) without giving up embeddings' chunk-level wins. Not attempted.
- **PDF ingestion.** Notices, handbooks, and fee schedules are frequently linked as PDFs on this site; the crawler now skips them cleanly (see above) but nothing extracts their text into the corpus yet.
- **Deployment.** `Dockerfile` and `requirements.txt` are here as a starting point, but nothing has actually been deployed anywhere live yet.
- **React frontend.** `frontend/index.html` is a plain-HTML stand-in that's now confirmed working end-to-end in a browser; the plan doc calls for React eventually, which is a straightforward swap once the API contract (see `api/main.py`) is settled.

## Security note

`REPORT.md` flags that the Groq API key used for testing was pasted into a chat transcript rather than kept purely in an environment variable. **Rotate that key** (revoke it in the Groq console and issue a new one) before relying on it further — treat any key that touched a chat transcript as compromised.

**Update (2026-09-21, REPORT5.md): the rotation done for round 5 was incomplete.** A new key was supplied and works, but the *old* key was checked directly and still returns HTTP 200 from Groq's API — creating a new key doesn't revoke the old one on its own. Both keys have now touched this chat's history, so both need to be treated as compromised. `RUNBOOK-6-PLACEMENTS-FIX-AND-KEY-CLEANUP.md` walks through actually deleting the old key in the Groq console and confirming it's dead (not just creating yet another new one).
