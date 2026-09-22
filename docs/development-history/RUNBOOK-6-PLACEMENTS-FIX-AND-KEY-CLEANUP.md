# Runbook 6: verify the placements fix, and actually revoke the old key

**Context:** `REPORT5.md` was genuinely good news — real embeddings work on this machine and fixed two of the three hard questions outright (Civil Engineering's intake number, the 5G lab's announcement date both now answer correctly with the right citation). The one still-failing question (Training & Placement stats) turned out to have a precise, different cause: splitting "How many students got placed in 2025-26 and how many companies came?" into two sub-questions loses the shared context ("placement") that only the whole question carries — you confirmed the actual stats chunk ("more than 678 students... over 170 reputed organizations") ranks 2nd for the *whole* question, but neither half alone finds it.

Cowork fixed this in `pipeline/agent.py` and `pipeline/generate.py`: when a question gets split into sub-questions, it now *also* retrieves for the undivided question, and merges anything new from that into the context sent to the LLM (deduped, same size caps as before — purely additive, can't reopen the 429 risk). Tested in sandbox against the TF-IDF fallback index (no regression: benchmark still 95%, single-question flow unaffected) — but the actual fix only has a chance of working with the **real embeddings index already sitting on this machine** (per REPORT5.md, `data/processed/index.pkl` is already an embeddings index — no need to rebuild it, just pull the two updated Python files).

**Also, please actually finish the key rotation this time.** REPORT5.md found that creating a new Groq key didn't revoke the old one — the old key (`gsk_GIU...`, used and pasted in chat across rounds 1-4) still returns HTTP 200. A new key alongside a still-valid old one isn't a rotation, it's just a second key. Both keys are now in this chat's history, so both should be treated as compromised.

---

## Step 0 — setup

```bash
cd vnit-chatbot
```

Pull the updated `pipeline/agent.py` and `pipeline/generate.py`. No need to touch `data/processed/` or re-run `build_index.py` -- the embeddings index from REPORT5.md's run is still what you want.

## Step 1 — revoke the old key for real

1. Go to console.groq.com -> API Keys.
2. Find the key used in REPORT.md through REPORT4.md (starts `gsk_GIU...`).
3. **Delete/revoke it** (not just "create a new one" -- that's the step that was missed last time).
4. Confirm it's actually dead: `curl -sS https://api.groq.com/openai/v1/models -H "Authorization: Bearer <the old key>"` should now fail (401/403), not return HTTP 200 like it did in REPORT5.md.
5. Keep using the newer key from REPORT5.md going forward (or issue a fresh one if you'd rather not keep reusing one that's touched this chat either -- entirely reasonable at this point).

## Step 2 — re-test the placements question

```bash
export GENAI_API_KEY="<your current key>"
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "How many students got placed in 2025-26 and how many companies came?"}' | python3 -m json.tool

kill %1
```

**Observe:** does the answer now include the actual numbers (678 students / 170+ organizations, or whatever the current page says), correctly cited to the TNP/placements page? If it's still "not found," check whether `data/processed/index.pkl` is actually the embeddings index (REPORT5.md's Step 1 confirms it should be) -- the merge fix only helps if the underlying retrieval can find the right chunk *somewhere*, which REPORT5.md showed only happens with embeddings, not TF-IDF.

## Step 3 — quick regression check

Run the benchmark once more just to confirm nothing broke:

```bash
cd pipeline
python3 evaluate.py
```

**Observe:** should still be 17/19 = 89% (the embeddings number from REPORT5.md) or better -- not worse. This change doesn't touch retrieval scoring, only which already-retrieved chunks get sent to the LLM, so it shouldn't move this number, but worth confirming.

---

## `REPORT6.md` — create this file with your findings

```markdown
# Placements fix and key cleanup

Run on: <date>

## Step 1 — old key revoked?
Confirmed dead: <yes/no>
(paste the curl result showing 401/403, or explain if still valid)

## Step 2 — placements question re-test
mode: <...>
sources: <...>
answer: <paste>
Fixed?: <yes/no/partially>

## Step 3 — benchmark regression check
Hit-rate: <n>/19 = <pct>

## Anything else worth flagging
<free text>
```

Save as `REPORT6.md` in this `vnit-chatbot/` folder.
