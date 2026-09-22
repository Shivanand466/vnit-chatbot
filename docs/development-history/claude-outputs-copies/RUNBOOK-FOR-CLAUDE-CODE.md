# Runbook: verify the two blocked pieces (hand this to Claude Code)

**Context for whoever/whatever is reading this:** this project (`vnit-chatbot/`) is a pilot RAG chatbot for the VNIT website, built by Claude running in a cloud sandbox for Shivanand. Everything in it works and was tested *except two things*, because that sandbox's network is restricted to package registries only — it cannot reach `vnit.ac.in`, `huggingface.co`, or any LLM API host. Running on Shivanand's own machine via a normal terminal (which is what's happening if you're reading this as Claude Code) should have ordinary internet access, so you should be able to actually finish verifying these.

Full background: `README.md` in this same folder ("What hasn't been tested, and exactly why"). The project's shared status doc (readable from the Cowork session) has the same history if useful context is missing here.

**Your job:** run each step below, observe exactly what happens, and write it all into `REPORT.md` (template at the bottom — create it in this same folder) so the Cowork session can read it back later. Don't skip a step because an earlier one failed — note the failure in `REPORT.md` and move to the next step anyway; partial results are still useful.

---

## Step 0 — setup

```bash
cd vnit-chatbot   # this folder
pip install -r requirements.txt
python3 pipeline/chunk.py
python3 pipeline/build_index.py
python3 pipeline/evaluate.py
```

**Observe:** the hit-rate line `evaluate.py` prints (should be something like `Retrieval hit-rate (top-3): 19/19 = 100%`). Record the exact numbers — if it's changed from 100%, that's worth flagging, not hiding.

## Step 1 — confirm real internet reaches vnit.ac.in from this machine

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://vnit.ac.in --max-time 15
```

**Observe:** the HTTP status code. `200` confirms this machine isn't behind the same block Claude's sandbox was. Anything else (or a curl error) — record the exact error text.

## Step 2 — get a free LLM API key

Pick ONE:

- **Groq** (recommended, generous free tier, fast): go to console.groq.com, sign up (Google/GitHub login works), go to "API Keys", create a new key. Base URL is `https://api.groq.com/openai/v1`, model `llama-3.1-8b-instant` — these are already the defaults in `pipeline/generate.py`, so you only need the key itself.
- **OpenRouter** (more model choice, some free models): go to openrouter.ai, sign up, create a key under "Keys". Use base URL `https://openrouter.ai/api/v1` and a free model id such as `meta-llama/llama-3.1-8b-instruct:free`.

Set the environment variable(s) in your shell:

```bash
export GENAI_API_KEY="<the key you just created>"
# only needed if you picked OpenRouter instead of Groq:
export GENAI_BASE_URL="https://openrouter.ai/api/v1"
export GENAI_MODEL="meta-llama/llama-3.1-8b-instruct:free"
```

**Observe:** which provider you used (don't put the actual key value in `REPORT.md` — just note "Groq" or "OpenRouter").

## Step 3 — run the API and test a real LLM-composed answer

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -sS -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "What is the fee for B.Tech and where can I find the hostel rules?"}' | python3 -m json.tool
```

**Observe, specifically:** the `"mode"` field in the response.
- If it says `"llm (llama-3.1-8b-instant)"` (or whatever model you used) — **it worked**. Copy the full JSON response into `REPORT.md`.
- If it says `"extractive (LLM call failed: ...)"` — the LLM call failed. Copy the *exact* error text after "LLM call failed:" into `REPORT.md` — that tells us whether it's an auth problem, a rate limit, a wrong model name, or something else.
- If it says `"extractive (no GENAI_API_KEY set)"` — the environment variable didn't carry into the process that ran uvicorn (common if you used a different terminal/shell than the one where you `export`ed it). Re-check Step 2 was run in the *same* shell session, or pass it inline: `GENAI_API_KEY=... uvicorn api.main:app ...`.

Try 2-3 different questions (single-part and multi-part like the example above) and record each `mode` value.

When done: `kill %1` to stop the server (or find and kill the uvicorn process another way).

## Step 4 — open the frontend in a real browser

With the API still running (repeat step 3's `uvicorn ... &` if you stopped it):

1. Open `frontend/index.html` directly in a browser (double-click it, or `open frontend/index.html` / `start frontend/index.html`).
2. Confirm the API URL field at the top says `http://localhost:8000/ask`.
3. Type a question and hit "Ask".

**Observe:** does an answer appear with sources listed below it? Any errors in the browser's console (F12 → Console tab)? Note both.

## Step 5 — confirm a real crawl is now possible (don't need to crawl everything, just prove it)

```bash
python3 -c "
import requests
r = requests.get('https://vnit.ac.in/section/academics/admission', timeout=15)
print('status:', r.status_code)
print('length:', len(r.text))
print(r.text[:300])
"
```

**Observe:** did this succeed (status 200, real HTML back) where it failed inside Claude's sandbox? This confirms `pipeline/recrawl.py`'s fetch step (currently a stub) could be filled in for real from this machine. You don't need to actually build out the full crawler now — just confirm the door is open.

---

## `REPORT.md` — create this file with your findings

```markdown
# Verification report

Run on: <date>
Machine: <brief description, e.g. "Windows laptop, WSL" or "macOS">

## Step 0 — retrieval benchmark
Hit-rate: <paste the exact line>

## Step 1 — direct internet to vnit.ac.in
HTTP status: <code, or error text>

## Step 2 — LLM provider used
Provider: <Groq / OpenRouter / other>
(no key values here)

## Step 3 — LLM-composed answers
Question 1: "<question>"
  mode: <exact mode string>
  (if llm mode worked) answer: <paste it>
  (if it failed) error: <exact error text>

Question 2: "<question>"
  mode: <...>

## Step 4 — frontend
Loaded and got an answer: <yes/no>
Browser console errors: <none / paste them>

## Step 5 — direct crawl test
Status: <200 / error>
Notes: <anything unexpected>

## Anything else worth flagging
<free text>
```

Save that as `REPORT.md` in this same `vnit-chatbot/` folder. The Cowork session will read it from there on its next pass over this project.
