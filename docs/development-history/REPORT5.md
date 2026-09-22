# Real embeddings attempt

Run on: 2026-09-21 (Windows 11, Git Bash + Anaconda Python 3.13.5, via Claude Code). No project code was modified. `data/processed/index.pkl` was rebuilt as an embeddings index (it is now an embeddings index, not TF-IDF, on disk). To go back to TF-IDF, re-run `build_index.py` after uninstalling `sentence-transformers`, or ask for a switch.

Note on the request: the user typed "Open RUNBOOK-2" along with a new key; RUNBOOK-2 was already complete and unchanged, so I confirmed with the user that Runbook 5 (the newest, and the one that needs a key) was intended.

## Step 1 — did it reach huggingface.co?
Outcome: **embeddings mode worked.** huggingface.co returned HTTP 200 from this machine, and `build_index.py` printed `[embeddings] Loading sentence-transformers/all-MiniLM-L6-v2 ...`, `[embeddings] Encoding 417 chunks...`, `[embeddings] Indexed 417 chunks (dim 384)`, `Saved embeddings index -> .../data/processed/index.pkl`. No `[fallback]` line.
Model download + encoding time: ~46 seconds total for the run (encoding itself ~16 s on CPU for 417 chunks).
Install: `pip install -r requirements.txt` took a few minutes and pulled in torch 2.14.0, transformers 5.17.0, sentence-transformers 6.1.0, huggingface-hub 1.32.0. **Side effect on the Anaconda environment:** it upgraded `click` 8.1.8 → 8.5.0 and `setuptools` → 84.0.0 (numpy stayed 2.1.3, scikit-learn 1.6.1). Nothing broke that I saw, but it changes the shared Anaconda env, not a venv.
Harmless warnings on load: unauthenticated HF Hub requests (set `HF_TOKEN` for higher limits) and "cache-system uses symlinks ... your machine does not support them" (Windows without Developer Mode; caching still works, just uses more disk).

## Step 2 — benchmark comparison
Embeddings hit-rate: **17/19 = 89%**   (TF-IDF baseline: 18/19 = 95%)  -> **slightly worse overall.**
Which questions changed:
- **Newly passing:** "How many students got placed in 2025-26 and how many companies came?" — the question that failed every previous round. `tnp` is now top-1 and top-2 for the whole question.
- **Still missing (TF-IDF also missed):** "What specializations does the Electrical Engineering M.Tech offer?" — top result was `engineering/mining`; the electrical page is at rank 11 and 17 for that query.
- **Newly missing (TF-IDF passed):** "What is the phone number for the Registrar's Office?" — expected `contact-us`, top result was `rti-officer`; `contact-us` is at rank 4 (just outside top 3).
So the embeddings are not a strict win on the benchmark: net -1, but they trade one chronic failure for a near-miss, and (Step 3/4) they do much better on the chunk-level cases that were actually causing wrong answers.

## Step 3 — the two known hard cases
Civil intake sentence ("intake of 120 students per year") — new rank: **1** (was 12 with TF-IDF).
5G announcement date ("October 27, 2023" / "announcement was made") — new rank: **1** (and 5) for "when was the 5G lab announced"; also rank 1 (and 3) for the un-decomposed "Tell me about the 5G lab and when was it announced" (was 4 and 9 with TF-IDF).
(I measured ranks with a small script over `retrieve(..., k=20)` instead of eyeballing `query.py` output; same retrieval function.)

## Step 4 — real LLM test
Groq, default model `openai/gpt-oss-20b` (no `GENAI_MODEL` set). No 429s or other errors; all three `mode: llm (openai/gpt-oss-20b)`.

Question: "How many undergraduate students does Civil Engineering enroll annually?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/engineering/civil/`, `https://vnit.ac.in/engineering/mining`
  answer: "The Civil Engineering department enrolls **120 undergraduate students per year** [Civil Engineering Department, VNIT Nagpur — https://vnit.ac.in/engineering/civil/]"
  **Correct and correctly cited. Fixed** (previously "not found" in REPORT3 and REPORT4).

Question: "Tell me about the 5G lab and when was it announced"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/5g-lab-vnit-nagpur`
  answer: A good description of the lab, then: "**Announcement** — The 5G use-case lab was announced during a virtual ceremony hosted by Prime Minister Narendra Modi at the Indian Mobile Congress (IMC-23) in New Delhi on **27 October 2023** [5G Lab VNIT Nagpur — https://vnit.ac.in/5g-lab-vnit-nagpur]."
  **Correct. Fixed** — first round where the announcement date is found.

Question: "How many students got placed in 2025-26 and how many companies came?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `notice-new`, `notice/`, `academic-programs`, `section/tnp/`, `engineering/mech/`, `centre-for-innovation`
  answer: "The passages you provided do not include any information about the number of students who were placed in 2025-26 or the number of companies that participated."
  **Still not answered, but now for a different, diagnosable reason.** The page has the facts: `data/raw/placements.txt` says "For the Placement Season 2025-26, more than 678 students ... secured employment ... offers were extended by over 170 reputed organizations". With embeddings, that chunk ranks **2nd for the whole question** — but `agent.py` decomposes the question into two sub-questions ("How many students got placed in 2025-26" and "how many companies came") and retrieves for each separately. I checked what reached the LLM: for sub-question 1 the top 3 were `notice-new`, `notice/`, `academic-programs` (tnp ranks 24th), and for sub-question 2 the top 3 were a different `tnp` chunk plus mech and centre-for-innovation. **The chunk with "678 students / 170 organizations" was in neither sub-question's top 3**, so the LLM honestly said it wasn't in the passages. The subject ("placement") is lost when the question is split, the same class of bug as the 5G "it" issue.

## Step 5 — API key
Rotated this time: **Yes** — a different key was supplied this round (`gsk_xor...`, verified valid against Groq's API, HTTP 200). No key values recorded here.
**But the old key is NOT revoked:** I checked and `gsk_GIU...` (used in REPORT.md through REPORT4.md, and pasted in chat) still returns HTTP 200 from `GET /openai/v1/models`. Creating a new key doesn't disable the old one; it needs to be **deleted in the Groq console** (console.groq.com -> API Keys). Until then the rotation has no security effect. Both keys are also now in this chat transcript.

## Anything else worth flagging
- **Verdict:** real embeddings are worth keeping. Benchmark is -1 (89% vs 95%) but that benchmark mostly tests page-level retrieval, whereas the embedding index fixed exactly the chunk-level failures that were hurting real answers (Civil 120/year, 5G date, placements chunk now in the top 2 for the full question). Two out of the three "hard" questions now answer correctly end to end, for the first time.
- **Next fix (highest value, and cheap):** the placements failure is now a decomposition/merge problem, not a retrieval-model problem. Retrieving for the *whole* question as well as each sub-question, and merging the chunks (deduped) into the prompt would have surfaced the 678/170 chunk. Alternatively, have `decompose()` carry the topic into each sub-question ("students placed in 2025-26" -> "placement 2025-26 students placed", "how many companies came for placement").
- **Hybrid scoring** (TF-IDF + embeddings) might recover the two benchmark misses: Registrar phone (`contact-us` at rank 4, a lexical "phone number" match TF-IDF gets) and Electrical M.Tech (both models struggle; the electrical page is at rank 11+).
- **Scores are lower and flatter with embeddings** (top results 0.5-0.7 vs 0.17-0.19 before, but with less separation between the 1st and 3rd), so `agent.py`'s conflict/recency heuristics that use score gaps may behave differently. Not investigated.
- **Cold-start cost:** the API process loads the MiniLM model on the first `/ask` (a few seconds) and caches it after; the `Dockerfile` will need `sentence-transformers` installed (torch makes the image much larger) and ideally the model pre-downloaded at build time, or it will download it on the first request in production.
- Server stopped, port 8000 free; server log kept in Claude Code's scratchpad, not the project.
