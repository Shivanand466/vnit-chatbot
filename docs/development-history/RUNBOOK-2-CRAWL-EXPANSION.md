# Runbook 2: expand the corpus for real, and refresh what's there

**Context:** the previous runbook (`RUNBOOK-FOR-CLAUDE-CODE.md`) confirmed the LLM path, the frontend, and that this machine has real internet to vnit.ac.in — see `REPORT.md`. This runbook uses that confirmed internet access to do the two things that were still just stubs: actually expand the page corpus beyond the original 19, and actually re-crawl those 19 for real (rather than via Claude's WebFetch tool, which paraphrases through a small model).

New code since last time: `pipeline/fetch_utils.py` (real HTTP fetch + robots.txt check + link extraction), `pipeline/crawl.py` (bounded BFS crawler), and `pipeline/recrawl.py` (now actually implemented, was a stub before). Install `beautifulsoup4` if `pip install -r requirements.txt` hasn't been re-run since these were added.

As before: run every step even if an earlier one has issues, write everything you observe into `REPORT2.md` (template at the end), and don't fill in numbers you didn't actually see.

---

## Step 0 — setup

```bash
cd vnit-chatbot
pip install -r requirements.txt
```

## Step 1 — re-crawl the existing 19 pages for real

```bash
cd pipeline
python3 recrawl.py
```

**Read the module docstring's caveat before this**: since the original 19 pages were fetched via Claude's WebFetch tool (which paraphrases through a small model), expect most/all of them to show `[CHANGED]` on this *first* real run — that's the extraction method improving (real verbatim text now), not 19 real edits to the website. Note in `REPORT2.md` how many showed `[CHANGED]` vs `[unchanged]` vs `[STALE]`, and if any are `[STALE]`, paste the error next to them (that's a real signal — a page that's moved or is now blocked).

## Step 2 — expand the corpus with a real crawl

```bash
python3 crawl.py --max-pages 60 --max-depth 3
```

This discovers and fetches new pages by following links from the homepage, skipping anything already in `data/raw/` and anything matching the skip-list in `crawl.py` (admin logins, webmail, etc.). 60 pages / depth 3 is a reasonable first batch — feel free to go higher (e.g. `--max-pages 150`) if it finishes quickly and you want broader coverage, but note whatever number you actually used.

**Observe and record:**
- How many new pages got saved (the script prints this).
- How many were skipped by robots.txt vs by the skip-list.
- Any errors, and how many.
- Roughly how long the crawl took (it's deliberately rate-limited to ~1 request/second to be polite to the site, so 60 pages ≈ a couple of minutes minimum).

## Step 3 — rebuild the index and re-check accuracy

```bash
python3 chunk.py
python3 build_index.py
python3 evaluate.py
```

**Observe:** the new chunk count and vocab size (will be larger than before), and the hit-rate. A drop from 100% wouldn't be alarming on its own — the benchmark's `evaluate.py` list only covers the original 19 pages' topics, so a much bigger corpus gives TF-IDF more (irrelevant) chunks to potentially rank higher by accident. If it drops, paste which questions now miss and what came back instead — that's useful signal for whether TF-IDF is starting to strain and real embeddings (see README, "Still not built") are worth prioritizing.

## Step 4 — spot-check a few questions against the expanded corpus

Pick 3-4 questions that specifically target pages you *know* are new from Step 2 (look at what `crawl.py` printed). Run them through the full pipeline with a real LLM answer, same as before:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "<your question about a newly-crawled page>"}' | python3 -m json.tool
```

(Remember `GENAI_API_KEY` needs to be set in this shell — re-export it if this is a fresh terminal. Use the *rotated* key if you followed the previous runbook's security recommendation.)

**Observe:** does it find and cite the new page correctly? Record 2-3 full examples.

## Step 5 — a note on PDFs

`crawl.py` currently skips anything that isn't an HTML page, which means linked PDFs (rulebooks, notices, fee schedules) are NOT being pulled in yet, even though the plan doc calls for them eventually. Not asking you to build PDF extraction in this pass — just note in `REPORT2.md` roughly how many PDF links you noticed being skipped (a rough count from watching the crawl output is fine), so it's clear how much is left on the table.

---

## `REPORT2.md` — create this file with your findings

```markdown
# Crawl expansion report

Run on: <date>

## Step 1 — re-crawl of existing 19 pages
Changed: <n>   Unchanged: <n>   Stale: <n>
(If any stale, list them with their errors.)

## Step 2 — new crawl
Pages/depth used: --max-pages <n> --max-depth <n>
New pages saved: <n>
Skipped by robots.txt: <n>
Skipped by pattern: <n>
Errors: <n>
Time taken: <roughly>

## Step 3 — rebuilt index
Chunks: <n>   Vocab size: <n>
Benchmark hit-rate: <e.g. 19/19 = 100%>
(If it dropped, list which questions missed and what came back instead.)

## Step 4 — spot-checks on new pages
Question 1: "<question>"
  mode: <...>
  Correctly cited the new page: <yes/no>
  answer: <paste>

Question 2: ...

## Step 5 — PDFs noticed but not fetched
Rough count: <n>
Examples of what they looked like (titles/URLs if you noted any): <...>

## Anything else worth flagging
<free text>
```

Save as `REPORT2.md` in this `vnit-chatbot/` folder.
