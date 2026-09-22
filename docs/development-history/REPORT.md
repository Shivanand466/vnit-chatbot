# Verification report

Run on: 2026-09-21
Machine: Windows 11, Git Bash (MSYS) + Anaconda Python 3.13.5, run via Claude Code (not the sandbox)

## Step 0 — retrieval benchmark
Hit-rate: `Retrieval hit-rate (top-3): 19/19 = 100%`
(35 chunks indexed from 19 source files, vocab size 3282 — matches the sandbox's prior result.)

## Step 1 — direct internet to vnit.ac.in
HTTP status: `200`
Confirms this machine is not behind the sandbox's egress block.

## Step 2 — LLM provider used
Provider: Groq
(no key values recorded here)

**Important finding:** the model name hardcoded as the default in `pipeline/generate.py`
(`llama-3.1-8b-instant`) has been **retired from Groq's lineup** — it no longer appears in
`GET https://api.groq.com/openai/v1/models` and a direct call to it returns:
```
{"error":{"message":"The model `llama-3.1-8b-instant` does not exist or you do not have access to it.","type":"invalid_request_error","code":"model_not_found"}}
```
This is a real API-side change (the model was live when `generate.py` was written, per the file's
own 2026-09-21 note, and is gone now), not a key or network problem. Worked around by setting
`GENAI_MODEL=openai/gpt-oss-20b` (currently listed, fast, free-tier), which succeeded — see Step 3.
**Recommend updating the default in `pipeline/generate.py` line 72** away from
`llama-3.1-8b-instant` to a currently-active model (e.g. `openai/gpt-oss-20b` or
`llama-3.3-70b-versatile`, whichever Groq is currently serving) so a fresh setup doesn't
silently fall back to extractive mode.

## Step 3 — LLM-composed answers
(All three run with `GENAI_MODEL=openai/gpt-oss-20b` after the Step 2 model-name fix.)

Question 1: "What is the fee for B.Tech and where can I find the hostel rules?"
  mode: `llm (openai/gpt-oss-20b)`
  answer: "**B.Tech fee** — The passage titled "Fees Information – VNIT Academic Section" indicates
  that the institute publishes a "4-Year Fee Estimate for Bachelor of Technology." However, the
  exact amount of the B.Tech fee is not specified in the provided excerpts. Source: "Fees
  Information" — https://vnit.ac.in/section/academics/fees/ / **Where to find hostel rules** —
  The detailed hostel facilities and services are described in the passage titled "Hostel Section
  – VNIT Nagpur Hostel Section." While this passage lists amenities and general management, it
  does not explicitly provide the hostel rules. Those rules would typically be found on the
  hostel section's webpage (or in related hostel policy documents), but such a document is not
  included in the excerpts provided. Source: "Hostel Section" — https://vnit.ac.in/section/hostel/"

Question 2: "What documents are required for admission?"
  mode: `llm (openai/gpt-oss-20b)`
  answer: "The passages provided do not contain any information about the specific documents
  required for admission to VNIT."
  (Correctly declined to guess rather than hallucinate — matches the prompt's instruction.)

Question 3: "Who is the director of VNIT and what departments does the institute offer?"
  mode: `llm (openai/gpt-oss-20b)`
  answer: "**Director of VNIT Nagpur** — Prof. (Dr.) Prem Lal Patel is the current Director of
  Visvesvaraya National Institute of Technology (VNIT) Nagpur. He assumed office on 21 May 2024
  and also serves as President of ISH. (Source: Director, VNIT Nagpur) / **Departments offered by
  VNIT Nagpur** — From the provided passages, the only department explicitly mentioned is the
  Civil Engineering Department. It offers undergraduate, postgraduate, and doctoral programmes in
  civil engineering and related fields. (Source: Civil Engineering Department)"

**Encoding note:** piping curl's raw response through `python -m json.tool` on this Windows/Git
Bash setup produced visible mojibake (e.g. em-dashes rendered as `Ã¢â‚¬â€`) because `json.tool`
reads stdin using the console's codepage, not UTF-8. Re-checked by saving the response to a file
and loading it with `open(..., encoding="utf-8")` — the actual bytes are correct UTF-8, no bug in
the API/pipeline itself. Flagging only so nobody chases a phantom encoding bug based on
terminal-piped output on Windows.

## Step 4 — frontend
Loaded and got an answer: **yes**
Tested live in browser with the question "Are foreigners allowed to study in vnit" — got a full
LLM-composed answer citing DASA/SII/ICCR admission routes, with "Sources: Admissions" and
`mode: llm (openai/gpt-oss-20b)` displayed under the answer, exactly as designed.

Browser console errors: One message logged, not a functional error:
```
Unsafe attempt to load URL file:///.../frontend/index.html from frame with URL
file:///.../frontend/index.html. 'file:' URLs are treated as unique security origins.
```
This is a benign browser warning tied to opening the page via `file://` (likely a same-page
resource/favicon probe blocked by that origin policy) — the actual `/ask` fetch to
`localhost:8000` still worked and the answer rendered correctly. Not something to fix unless the
frontend is later served over `http://` instead of opened as a local file.

## Step 5 — direct crawl test
Status: `200`
Notes: Fetched `https://vnit.ac.in/section/academics/admission` directly with `requests` —
got back 231,338 bytes of real HTML (starts with `<!DOCTYPE html>...<title>Admission –`).
Confirms `pipeline/recrawl.py`'s fetch step is unblocked on this machine and could be filled in
for real; the failure was specific to the sandbox's proxy, not the target site or the code.

## Anything else worth flagging
- The only real blocker found was the stale Groq model name (Step 2) — everything else in the
  runbook worked exactly as the sandbox predicted it would once given a normal network.
- Practical note for whoever re-runs this: on Windows, backgrounding `uvicorn` with `&` in one
  Bash tool call and then `kill %1` in a *different* call won't work — each call is a fresh shell,
  so job-control state (`%1`) doesn't carry over. Find the real PID via
  `netstat -ano | grep ":8000"` and `taskkill //F //PID <pid>` instead.
- Recommend rotating the Groq API key used during this test session since it was pasted directly
  into a chat transcript rather than kept purely in an environment variable.
