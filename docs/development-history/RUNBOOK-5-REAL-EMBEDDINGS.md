# Runbook 5: try real semantic embeddings for real

**Context:** every previous round confirmed TF-IDF is doing about as well as it can (95% on the benchmark, and two more attempts to squeeze out more — a date-boost heuristic and word-vector averaging — both made things worse on real measurement, see `EXPERIMENTS-LOG.md`). The clear next thing to try is a *real* sentence-embedding model (`sentence-transformers`), which needs to download model weights from huggingface.co. Cowork's own sandbox and device-bridge tooling are confirmed blocked from reaching huggingface.co — but every previous report from this machine (yours) confirms it has real, working internet (it reaches vnit.ac.in and Groq's API directly). huggingface.co specifically hasn't been tested from here yet — that's exactly what Step 1 checks.

Cowork already wrote the code for this and tested the fallback path (with TF-IDF) end to end — what's untested is the actual embeddings path, since that needs a working connection to huggingface.co that only exists on this machine.

**How it's built to behave:** `pipeline/build_index.py` now tries to build a real embeddings index first (using the small, fast `sentence-transformers/all-MiniLM-L6-v2` model, ~80MB, no GPU needed). If `sentence-transformers` isn't installed, or the model can't be downloaded for any reason, it automatically falls back to the same TF-IDF setup as before and says exactly why in the console output — it won't just crash. So this is safe to try: worst case, nothing changes.

---

## Step 0 — setup

```bash
cd vnit-chatbot
pip install -r requirements.txt
```

This now includes `sentence-transformers` (previously commented out). It's a bigger install than before (pulls in PyTorch) — give it a few minutes on a normal connection.

## Step 1 — rebuild the index and see which mode it picks

```bash
cd pipeline
python3 build_index.py
```

**Watch the first couple of lines of output carefully** — they tell you which path it took:

- If you see `[embeddings] Loading sentence-transformers/all-MiniLM-L6-v2 (downloads the model the first time this runs)...` followed by `[embeddings] Indexed 417 chunks (dim 384)` and `Saved embeddings index -> ...` — **it worked**, huggingface.co is reachable from this machine, and the index now uses real semantic embeddings. Note roughly how long the download + encoding took.
- If instead you see a `[fallback] ...` line — **it didn't reach huggingface.co either**, and it's using TF-IDF same as before (nothing broken, just no improvement yet). Paste the exact fallback message you see — the specific error (a network name-resolution failure looks very different from a 403 from a corporate proxy, and that difference tells us what's actually blocking it).

## Step 2 — re-run the benchmark and compare

```bash
python3 evaluate.py
```

**Observe:** the hit-rate. Compare directly against the TF-IDF baseline of **18/19 = 95%**. Any number is useful information here — better, same, or worse. If it's worse, that's a legitimate (if surprising) result, not something to hide — TF-IDF has now beaten one lighter-weight embedding attempt already (see `EXPERIMENTS-LOG.md`'s word-vector experiment), so it's not guaranteed a real transformer model automatically wins, though it's the most likely candidate to.

## Step 3 — specifically re-check the two known hard cases

These are the ones that were failing due to chunk-level ranking, not page-level (see `REPORT4.md`):

```bash
python3 query.py "How many undergraduate students does Civil Engineering enroll annually?" -k 10
python3 query.py "when was the 5G lab announced" -k 10
```

**Observe:** does the chunk containing "intake of 120 students per year" (Civil) or "October 27, 2023" / "announcement was made" (5G) now rank higher than it did with TF-IDF (it was rank 12 and rank 4/9 respectively)? You don't need to compute exact ranks by hand — just note whether the right-looking passage is now in the top 3-5 results or still buried further down.

## Step 4 — a real end-to-end LLM test, same as before

```bash
export GENAI_API_KEY="<your key>"
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "How many undergraduate students does Civil Engineering enroll annually?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "Tell me about the 5G lab and when was it announced"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "How many students got placed in 2025-26 and how many companies came?"}' | python3 -m json.tool

kill %1
```

**Observe:** do the Civil and 5G answers now include the actual numbers/dates? Does the Training & Placement question (the one benchmark question that's failed every single round so far) do any better?

## Step 5 — API key status

Same as every round: is this a rotated key, or the same one from before? Please actually rotate it this time if it's still the original — it's been reused across five test rounds now.

---

## `REPORT5.md` — create this file with your findings

```markdown
# Real embeddings attempt

Run on: <date>

## Step 1 — did it reach huggingface.co?
Outcome: <embeddings mode worked / fell back to TF-IDF>
If fallback, exact message shown: <paste>
If it worked, model download + encoding time: <roughly>

## Step 2 — benchmark comparison
Embeddings hit-rate: <n>/19 = <pct>   (TF-IDF baseline: 18/19 = 95%)
(If different from baseline, which questions changed and how?)

## Step 3 — the two known hard cases
Civil intake sentence -- new rank (or "still not in top 10"): <...>
5G announcement date -- new rank (or "still not in top 10"): <...>

## Step 4 — real LLM test
Question: "How many undergraduate students does Civil Engineering enroll annually?"
  mode: <...>
  answer: <paste>

Question: "Tell me about the 5G lab and when was it announced"
  mode: <...>
  answer: <paste>

Question: "How many students got placed in 2025-26 and how many companies came?"
  mode: <...>
  answer: <paste>

## Step 5 — API key
Rotated this time: <yes/no>

## Anything else worth flagging
<free text>
```

Save as `REPORT5.md` in this `vnit-chatbot/` folder.
