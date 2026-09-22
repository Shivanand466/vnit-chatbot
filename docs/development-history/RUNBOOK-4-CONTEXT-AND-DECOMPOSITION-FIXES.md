# Runbook 4: verify the sources-field and decomposition fixes

**Context:** `REPORT3.md` confirmed the chunking/vectorizer/rate-limit fixes all work for real, but surfaced two new, well-diagnosed bugs from the real LLM tests:

1. The API's `sources` field didn't match what was actually sent to the LLM — for the Electrical M.Tech question it named the *civil* department page, and for the 5G lab question it named an unrelated convocation page, even though the answer itself was drawn from (or should have been drawn from) different passages.
2. Query decomposition drops the subject in a trailing sub-question — "Tell me about the 5G lab **and when was it announced**" splits into a second sub-question ("when was it announced") that loses "5G lab" entirely, so retrieval for that half returns something unrelated.

Cowork found the root causes and fixed both in this sandbox (no real internet needed for the code fix itself, only for verifying it end-to-end, which is what this runbook is for):

- `generate.py` was only sending the **top-2** retrieved chunks per sub-question to the LLM, and reporting `sources` from the **top-1** only — regardless of which chunks actually made it into the prompt. REPORT3.md's Civil-enrollment and Electrical-M.Tech misses turned out to have the correct page sitting at **rank 3**, which was being retrieved (k=3) but never sent. Fixed: now sends up to top-3 per sub-question (still governed by the existing `MAX_CONTEXT_CHARS`/`MAX_CHUNK_CHARS` caps from last round, so this shouldn't reopen the 429 risk), and `sources` is now built from the exact chunks included in the prompt, not a separate top-1 lookup.
- `agent.py`'s `decompose()` now detects a bare referring pronoun (it/this/that/they/them/its/their) in a later sub-question and substitutes in the topic extracted from the sub-question before it. Verified locally: `decompose("Tell me about the 5G lab and when was it announced")` now returns `["Tell me about the 5G lab", "when was the 5G lab announced"]` instead of leaving "it" dangling.

One known limit, found while testing this: the 5G lab's actual announcement date sentence ranks **4th** for "when was the 5G lab announced" (0.169) — just outside the new top-3 cutoff (0.191/0.180/0.177, all from the same page but different sections). So the decomposition fix should measurably help retrieval find the *right page*, but this specific example may still not surface the *exact sentence* with the date. Worth checking either way.

---

## Step 0 — setup

```bash
cd vnit-chatbot
```

Confirm you have the updated `pipeline/generate.py` and `pipeline/agent.py` (both pushed after REPORT3.md). No `data/raw/` or `data/processed/` changes this round — don't need to re-run `chunk.py`/`build_index.py`.

## Step 1 — re-test the three previously-flagged questions with a real LLM call

```bash
export GENAI_API_KEY="<your key>"
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "What specializations does the Electrical Engineering M.Tech offer?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "How many undergraduate students does Civil Engineering enroll annually?"}' | python3 -m json.tool

curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "Tell me about the 5G lab and when was it announced"}' | python3 -m json.tool

kill %1
```

**Observe, for each:**
- Does `sources` now list the page you'd expect (electrical dept, civil dept) instead of the wrong one from REPORT3.md?
- For Civil/Electrical: does the answer text itself now contain the right fact (120 students/year; Integrated Power System + Power Electronics and Drives), correctly cited?
- For the 5G question: does the sub-question correctly stay about the 5G lab now (check if the answer's second half still says "not mentioned" for the announcement date, or if it found October 27, 2023 this time) — either outcome is useful to know, per the note above about rank 4.
- Any 429s or other errors.

---

## `REPORT4.md` — create this file with your findings

```markdown
# Sources-field and decomposition fixes verification

Run on: <date>

Question: "What specializations does the Electrical Engineering M.Tech offer?"
  mode: <...>
  sources: <...>
  answer: <paste>
  Fixed vs REPORT3.md?: <yes/no/partially>

Question: "How many undergraduate students does Civil Engineering enroll annually?"
  mode: <...>
  sources: <...>
  answer: <paste>
  Fixed vs REPORT3.md?: <yes/no/partially>

Question: "Tell me about the 5G lab and when was it announced"
  mode: <...>
  sources: <...>
  answer: <paste>
  Found the announcement date this time?: <yes/no>

Any errors this round: <...>

## Anything else worth flagging
<free text>
```

Save as `REPORT4.md` in this `vnit-chatbot/` folder.
