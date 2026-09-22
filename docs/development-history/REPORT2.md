# Crawl expansion report

Run on: 2026-09-21 (Windows 11, Git Bash + Anaconda Python 3.13.5, via Claude Code)

**Headline for Cowork:** the crawl itself worked cleanly (60 new pages, no robots/pattern skips, 2 harmless 404s), but expanding the corpus exposed a **chunking bug in `pipeline/chunk.py`** that the original 19 paraphrased pages had been hiding. It causes oversized chunks, a hit-rate drop, and Groq 429 errors. Details in Step 3 and "Anything else". No project code was modified; only `data/raw/` and `data/processed/` changed as a result of running the scripts. A backup of the original 19 pre-recrawl files is in Claude Code's scratchpad (not in the project).

## Step 1 — re-crawl of existing 19 pages
Changed: 19   Unchanged: 0   Stale: 0
As predicted by the docstring, all 19 changed on the first real run (verbatim text replacing WebFetch paraphrases). None unreachable. Took ~40 s.
Side effect worth knowing: word counts are now much larger for some pages (admissions 4,422 words, placements 2,438, library 2,069, notices 2,273).

## Step 2 — new crawl
Pages/depth used: --max-pages 60 --max-depth 3 (run through a thin wrapper script that calls `crawl.crawl()` unmodified, only to also record non-HTML responses)
New pages saved: 60 (data/raw now has 79 files)
Skipped by robots.txt: 0
Skipped by pattern: 0 (the SKIP_PATH_PATTERNS list never triggered in this batch)
Errors: 2, both `404 Not Found` on stale news-post URLs linked from the site (a "glimpses of IEEE SEFET 2026" post and a JRF-vacancy post). Nothing to fix on our side.
Time taken: ~180 s (~3 min)

Observations on the crawl output:
- The BFS reached breadth-first-shallow pages: home, department pages (mining, cvlsi, apm, maths, chemistry, humanities), administration (registrar, deans, BoG, telephone directory, recruitment), research (rnc/*, 5G lab, patents), sports, hostel notices, convocation, several news posts.
- **Near-duplicate pages were saved:** `/category/events` and `/index.php/category/events`; `/index.php/category/news` vs `/index.php/category/news-events`; `section/academics/notice-new` vs the existing `notice`. Crawler treats them as different URLs. Consider normalising `/index.php/` away and adding `/category/` and `/index.php/` to the skip list.
- Saved text still contains leftover navigation/menu text on some pages (e.g. the 5G-lab page starts "Sanchar Mitra / Contact Us / Events / About") because this site's theme does not wrap its menu in `<nav>`/`<header>`. Minor for now, but it adds noise to TF-IDF.

## Step 3 — rebuilt index
Chunks: 82   Vocab size: 24,985   (was 35 chunks / vocab 3,282)
Benchmark hit-rate: **17/19 = 89%** (was 19/19)

Misses:
- "How many students got placed in 2025-26 and how many companies came?" — expected `tnp`, top result was `https://vnit.ac.in/section/academics/notice-new`
- "What specializations does the Electrical Engineering M.Tech offer?" — expected `engineering/electrical`, top result was `https://vnit.ac.in/engineering/civil/`

**Root cause found — chunking bug:** 79 files produced only 82 chunks against a 150-word target. `chunk.py`'s `split_into_paragraphs()` splits on blank lines (`\n\s*\n`), but the real BeautifulSoup text from `fetch_utils.py` (`get_text(separator="\n")`) has essentially no blank lines, so nearly every page becomes ONE paragraph and therefore ONE chunk (`chunk_paragraphs` can only split *between* paragraphs). Measured: 37 of 82 chunks are over 300 words, 11 are over 1,000, largest is 4,391 words (admissions). The old WebFetch-paraphrased text happened to contain blank lines, which is why this never showed before.

**Experiment (on a scratch copy of the project; the real `chunk.py` is untouched):** changing that regex to `re.split(r"\n+", body)` gives 409 chunks, max 283 words, median 145, none over 300 — i.e. what was intended. Result: hit-rate **15/19 = 79%**. Extra misses: Civil enrolment and Chemical specializations questions, where `https://vnit.ac.in/academic-programs` now ranks above the department pages. So:
- Fixing chunking is clearly right for LLM context size (see Step 4), but it *lowers* the benchmark, because with real-sized chunks TF-IDF now has 409 candidates and several are from generic pages (academic-programs, notices, home) with overlapping vocabulary.
- That is the "TF-IDF strain" signal the runbook asked about: real embeddings (README "Still not built") now look worth prioritising, and/or boosting title/URL matches. Not attempted here.
- I did not apply the chunking change to the real project because it changes accuracy numbers and is a design call for Cowork.

## Step 4 — spot-checks on new pages
Setup: Groq, `GENAI_MODEL=openai/gpt-oss-20b` (the default in `generate.py` is still the retired `llama-3.1-8b-instant` — see REPORT.md — and I did not change it). I reused the original key from the previous session; I was not given a rotated one. No key values recorded here.

**Server A = real project as it stands (82 chunks, giant-chunk bug present)**
Server B = scratch copy with the `\n+` chunk fix (409 chunks)

Question 1: "Who are the deans of VNIT and what is the email of the Dean of Academic?"  (Server A)
  mode: `llm (openai/gpt-oss-20b)`
  Correctly cited the new page: **yes** — `https://vnit.ac.in/deans-2026`
  answer: Table of all six deans with emails, correctly giving Dean (Academic) Dr. V. R. Kalamkar, `deanacd@vnit.ac.in`, source "Deans — https://vnit.ac.in/deans-2026".

Question 2: "What is the VNIT 5G lab and when was it announced?"
  Server A mode: `extractive (LLM call failed: 429 Client Error: Too Many Requests for url: https://api.groq.com/openai/v1/chat/completions)` — reproduced twice, including after waiting out the rate window.
  Diagnosis: Groq's response headers for this model show `x-ratelimit-limit-tokens: 8000` (free tier tokens/minute). With giant chunks this request's context alone is ~5,700+ estimated tokens before prompt text and the model's reasoning tokens, so it hits the cap. This is a direct consequence of the chunking bug.
  Server B mode: `llm (openai/gpt-oss-20b)`; cited the new page (`https://vnit.ac.in/5g-lab-vnit-nagpur`): **yes**.
  answer (B): "The VNIT 5G Lab is a cutting-edge facility ... equipped with advanced hardware and software to explore and develop 5G communication technologies, IoT solutions, edge computing... key components include a 5G core, 5G radio, IMS, MEC server, IoT application development ... AR/VR/MR development, smart surveillance, device testing, and drone operations." Then, for the second half: "The passages provided do not contain information about the announcement date." (The page does say it was announced Oct 27, 2023 at IMC-23; the agent's sub-question split "when was it announced" lost the "5G lab" context and retrieved an unrelated convocation page — a decomposition weakness in `agent.py`, separate from chunking.)

Question 3: "Who is the Registrar of VNIT Nagpur?"  (Server B)
  mode: `llm (openai/gpt-oss-20b)`
  Correctly cited the new page: **partially** — answer: "Sachin Sudhakar Jagdale", cites "Board of Governors" and "Administrative Officers" passages (both real, both newly crawled). But the returned `sources` field lists only `https://vnit.ac.in/bog-2026`, so the API's `sources` list (top hit per sub-question) can disagree with what the LLM actually cited. Minor, worth aligning.

Question 4: "When and where is the 24th convocation of VNIT?"  (Server B)
  mode: `llm (openai/gpt-oss-20b)`
  Correctly cited the new page: **no.** Answer was vague ("scheduled for 2026 at VNIT Nagpur") and sources were just the homepage. The crawled page `instructions-to-degree-recipients-for-attending-24th-convocation-2026` has the exact date (15 Sept 2026, 7:30 AM, VNIT Auditorium) but did not rank in the top results — a retrieval miss (TF-IDF strain) not an LLM problem.

Question 5: "What is the vision of the sports section at VNIT?"  (A and B)
  mode: `llm (openai/gpt-oss-20b)` on both; both said the passages don't cover it and cited only the homepage. The `section/sports` page contains an explicit "Vision:" paragraph but wasn't retrieved. Another retrieval miss.

Summary: with the current corpus the LLM stage behaves well (declines to guess, cites sources, handles tables); the weak points are retrieval ranking on the larger corpus and the chunking bug.

## Step 5 — PDFs noticed but not fetched
Rough count: `crawl.py` doesn't count them (non-HTML responses are dropped silently, and only 5 PDFs were fetched-then-discarded before the 60-page cap stopped the crawl — e.g. `Institutions-Innovation-Council.pdf`, `website-committee-24.pdf`, `cad_cam_dept.pdf`, `water_resources_engineering_centre.pdf`, `remote_sensing_and_gis_lab1.pdf`). To get a better estimate I fetched 12 key pages separately and counted `.pdf` hrefs: **39 unique PDFs across those 12 pages** (per page: home 7, fees 1, admission 5, academic-programs 7, tnp 9, library 10, recruitment 8, rti-officer 7, academic-event-calendar 20; notice, hostel, rnc/forms-annexures 0). Extrapolating, the full site likely has hundreds.
Examples: `ESTABLISHMENT_MANUAL.pdf`, `Brochure-Final.pdf` (admission), `How-to-Pay-Application-Fee.pdf`, `Fees-for-NRI_Foreign-Nationals-for-DASA_ICCR_MEA-Admission.pdf`, `Electrical-Electronics-Engg-_Brochure_2025-26.pdf` (placements brochures).
Note: `fetch_utils.extract_internal_links` filters images/zip/Office docs but *not* `.pdf`, so PDFs are still downloaded in full and then thrown away — wasted requests/bandwidth; filtering `.pdf` out of the queue (or routing to a PDF handler) would save that.
Also note the fees page mostly lists fee estimates by title ("4 Year Fee Estimate for Bachelor of Technology", ...) with only 1 `.pdf` href in the static HTML; the actual fee numbers are behind PDFs/other links, so questions like the B.Tech fee amount can't be answered until PDF (or those links) are ingested — matches REPORT.md where the LLM said the fee amount wasn't in the passages.

## Anything else worth flagging
1. **Chunking bug (highest priority)** — see Step 3. One-line fix candidate: `re.split(r"\n+", body)` in `split_into_paragraphs()`; also consider a hard word-window fallback in `chunk_paragraphs()` so no single paragraph can exceed `CHUNK_WORDS`.
2. **`generate.py` should cap context** — even with sane chunks, it sends the top-2 chunks per sub-question with no size limit; on Groq's free 8,000 tokens/min limit that leads to 429s. A per-chunk truncation and/or a retry-with-shorter-context on 429 would help; also note the extractive fallback masks these failures behind `mode: "extractive (LLM call failed: 429 ...)"`.
3. **Stale default model** in `generate.py` (`llama-3.1-8b-instant`) is still unfixed — see REPORT.md.
4. **`agent.py` sub-question decomposition loses context** (e.g. "when was it announced" → retrieves an unrelated page). Consider carrying the main subject into sub-questions.
5. **Crawler hygiene** — near-duplicate URLs (`/index.php/...`, `/category/...`), leftover nav text, and no PDF counting (see Step 2/5).
6. Key handling: the same Groq key from the previous session was used; if it hasn't been rotated yet, that should still happen.
7. State of the project on disk now: `data/raw/` = 79 files (19 refreshed + 60 new), `data/processed/` built from them with the *unchanged* `chunk.py` (82 chunks). The experiment copy with the chunk fix lives only in Claude Code's scratchpad, not in the project.
