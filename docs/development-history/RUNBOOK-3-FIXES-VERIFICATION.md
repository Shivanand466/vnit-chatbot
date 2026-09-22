# Runbook 3: verify the post-crawl fixes for real

**Context:** `REPORT2.md` (your last report) surfaced real bugs once the corpus went from 19 hand-picked pages to a real 79-page crawl: a chunking bug that collapsed most pages into one oversized chunk, a resulting retrieval-accuracy drop, Groq 429 rate-limit risk from those oversized chunks, and some crawler hygiene issues (near-duplicate URLs, PDFs being fully downloaded then discarded). Cowork fixed all of these in `pipeline/chunk.py`, `pipeline/build_index.py`, `pipeline/generate.py`, `pipeline/crawl.py`, and `pipeline/fetch_utils.py`, and re-ran the pipeline against the real 79-page corpus already on this machine — but Cowork's sandbox still can't call the real Groq API or hit vnit.ac.in, so those two things need verifying here, on this machine, same as before.

Numbers Cowork got re-running locally against your existing `data/raw/` (79 files, unchanged) with the fixed code: `chunk.py` → 417 chunks (was 82). `build_index.py` → vocab size 11187. `evaluate.py` → **18/19 = 95%** hit-rate (was 89% before the chunking bug was found, dropped to 74% right after fixing chunking alone, recovered to 95% after also tuning the vectorizer). The one remaining miss is the Training & Placement stats question — expected, see `README.md`.

As before: run every step even if an earlier one has issues, write everything you observe into `REPORT3.md` (template at the end), and don't fill in numbers you didn't actually see.

---

## Step 0 — setup

```bash
cd vnit-chatbot
pip install -r requirements.txt
```

Pull the updated files if you haven't already (`chunk.py`, `build_index.py`, `generate.py`, `crawl.py`, `fetch_utils.py` all changed; `data/processed/chunks.jsonl` and `data/processed/index.pkl` were also regenerated and pushed — if those two are already present and recent, you can skip straight to confirming the numbers rather than rebuilding).

## Step 1 — confirm the chunking fix and benchmark, on this machine

```bash
cd pipeline
python3 chunk.py
python3 build_index.py
python3 evaluate.py
```

**Observe:** chunk count (expect 417), vocab size (expect 11187), and the hit-rate (expect 18/19 = 95%, missing only the Training & Placement question). If your numbers differ from these, say so exactly — don't round to match what's expected. A different `data/raw/` (e.g. if you've re-crawled since REPORT2.md) is a legitimate reason for different numbers; note if that's the case.

## Step 2 — real LLM call against the fixed pipeline

This is the part Cowork's sandbox can't do. Same as before:

```bash
export GENAI_API_KEY="<your Groq key — rotated one, if you followed the earlier security recommendation>"
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2
```

Then re-run the specific questions that were previously failing retrieval (from REPORT2.md's Step 3 misses) or hitting Groq 429s (from REPORT2.md's Step 4 spot-checks), now that both the chunking and the context-size fixes are in:

```bash
curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "When was the Mechanical Engineering department established?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "What specializations does the Electrical Engineering M.Tech offer?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "How many undergraduate students does Civil Engineering enroll annually?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "What two specializations does Chemical Engineering offer?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "How many students got placed in 2025-26 and how many companies came?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "Tell me about the 5G lab and when was it announced"}' | python3 -m json.tool
```

**Observe, for each:**
- `mode` — should read `llm (openai/gpt-oss-20b)`, not an `extractive (...)` fallback. If any come back `extractive (LLM call failed: ...)`, paste the full error — that tells us if the 429 fix actually worked or if something else is going on.
- Whether the `sources` field cites the page you'd expect (mech/electrical/civil/chemical department pages, TNP placements page).
- The actual answer text — does it look right, including the Training & Placement one, which we already know retrieval alone won't find the right page for (worth seeing what the LLM does when given the wrong context: does it hedge honestly, or confidently make something up?).

```bash
kill %1  # stop the uvicorn server started above
```

## Step 3 — API key status

Just confirm in `REPORT3.md`: is this a rotated key (different from the one used in the previous two rounds), or the same one reused again? If it's still the same un-rotated key, that's fine to keep testing with, but say so plainly rather than letting it go unmentioned a third time.

---

## `REPORT3.md` — create this file with your findings

```markdown
# Fixes verification report

Run on: <date>

## Step 1 — chunking fix + benchmark, re-run locally
Chunks: <n>   Vocab size: <n>
Benchmark hit-rate: <e.g. 18/19 = 95%>
(If different from expected, say what and why if known.)

## Step 2 — real LLM calls against the fixes
Question: "When was the Mechanical Engineering department established?"
  mode: <...>
  sources: <...>
  answer: <paste>

Question: "What specializations does the Electrical Engineering M.Tech offer?"
  mode: <...>
  sources: <...>
  answer: <paste>

Question: "How many undergraduate students does Civil Engineering enroll annually?"
  mode: <...>
  sources: <...>
  answer: <paste>

Question: "What two specializations does Chemical Engineering offer?"
  mode: <...>
  sources: <...>
  answer: <paste>

Question: "How many students got placed in 2025-26 and how many companies came?"
  mode: <...>
  sources: <...>
  answer: <paste>

Question: "Tell me about the 5G lab and when was it announced"
  mode: <...>
  sources: <...>
  answer: <paste>

Any 429s or other errors this round: <...>

## Step 3 — API key
Rotated since last time: <yes/no>

## Anything else worth flagging
<free text>
```

Save as `REPORT3.md` in this `vnit-chatbot/` folder.
