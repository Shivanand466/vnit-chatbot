# Fixes verification report

Run on: 2026-09-21 (Windows 11, Git Bash + Anaconda Python 3.13.5, via Claude Code). No project code was modified in this round; only the scripts were run (which regenerate `data/processed/`).

## Step 1 — chunking fix + benchmark, re-run locally
Chunks: 417   Vocab size: 11187
Benchmark hit-rate: 18/19 = 95%
Exactly matches Cowork's expected numbers. `data/raw/` was still the same 79 files (no re-crawl since REPORT2), and the updated `pipeline/*.py` files (chunk, build_index, generate, crawl, fetch_utils) were present on disk.
Only miss: "How many students got placed in 2025-26 and how many companies came?" — expected `tnp`, top result was `https://vnit.ac.in/section/hostel/notices`.

Also confirmed: the default model in `generate.py` is now `openai/gpt-oss-20b`. I deliberately did NOT set `GENAI_MODEL` in this round, so every answer below exercised that new default and it works.

## Step 2 — real LLM calls against the fixes
All six ran sequentially against one server with the real Groq API. **All six returned `mode: llm (openai/gpt-oss-20b)`; zero 429s and zero fallbacks to extractive.**

Question: "When was the Mechanical Engineering department established?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/engineering/mech/`  (correct page)
  answer: "I'm sorry, but the provided passages do not contain information about when the Mechanical Engineering department was established."
  Check against the raw page: **false negative.** `data/raw/mech_department.txt` says "Department of Mechanical Engineering is the oldest department started from the inception of the institute (1960)." Retrieval found the right page but the chunk sent to the LLM apparently wasn't the one containing that sentence (or the LLM didn't accept "inception (1960)" as an answer). Honest hedge, but the answer exists.

Question: "What specializations does the Electrical Engineering M.Tech offer?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/engineering/civil/`  (WRONG page listed)
  answer: "The M.Tech in Electrical Engineering offers specializations in **Integrated Power System** and **Power Electronics** (Academic Programs)."
  Check: the answer itself is **correct** (`eee_department.txt`: "Integrated Power System (IPS) and Power Electronics and Drives (PED)"), and it was drawn from the Academic Programs page. But the API's `sources` field lists the *civil* department page — so `sources` disagrees with what the answer actually cites. Still the benchmark miss category (electrical page not returned); the fixes just let the LLM find the answer elsewhere.

Question: "How many undergraduate students does Civil Engineering enroll annually?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/academic-programs`  (expected the civil department page)
  answer: "The passages you provided do not contain information about the number of undergraduate students enrolled annually in Civil Engineering."
  Check: **retrieval miss.** `civil_department.txt` says "It has an intake of 120 students per year under UG Course and 100 per year under PG Courses." The civil page's chunk didn't make the top results; the `academic-programs` page outranks it (same problem as in REPORT2). The LLM hedged honestly rather than guessing.

Question: "What two specializations does Chemical Engineering offer?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/engineering/chemical/`  (correct)
  answer: "The Chemical Engineering Department offers two specializations: **Chemical Engineering** and **Chemical Technology**【VNIT Nagpur Chemical Engineering Department】."
  Check: correct (raw page lists "Specialization / Chemical Technology / ..."). Fully working.

Question: "How many students got placed in 2025-26 and how many companies came?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/section/hostel/notices`, `https://vnit.ac.in/centre-for-innovation`  (neither is the placements page)
  answer: "The passages provided do not contain any information about the number of students placed or the number of companies that came in the 2025-26 academic year." followed by a bullet list of the four irrelevant pages it was given (Hostel notices, Academic notice, Centre for Innovation, CSE department) and why each doesn't help, ending "that information cannot be supplied from the given passages."
  **This answers the runbook's question about wrong-context behavior: given the wrong pages, the LLM hedged honestly and made nothing up.** No hallucinated numbers. (Placements data does exist on `section/tnp/`; the retrieval still can't find it — expected per Cowork.)

Question: "Tell me about the 5G lab and when was it announced"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/5g-lab-vnit-nagpur`, `https://vnit.ac.in/instructions-to-degree-recipients-for-attending-24th-convocation-2026`
  answer: A good multi-paragraph description of the 5G lab (hands-on platform, IoT, edge computing, 5G core and radio, internship/project support), then: "**Announcement date** — The provided passages do not mention when the 5G Lab was announced."
  Check: first half good. Second half is a **false negative that persists from REPORT2**: the 5G page itself says the selection was announced at a virtual ceremony at IMC-23 on 27 October 2023, but the sub-question "when was it announced" is retrieved on its own (losing "5G lab") and pulls the unrelated convocation page. This is the `agent.py` decomposition weakness I flagged last time; the chunking/context fixes don't address it. The `sources` field again includes the irrelevant convocation page.

Any 429s or other errors this round: **None.** The context-size fix in `generate.py` (chunk truncation + total context ceiling) evidently works: the 5G question, which 429'd on every attempt last round, now succeeds, and six back-to-back requests stayed under Groq's 8,000 tokens/min cap for this model.

## Step 3 — API key
Rotated since last time: **No, as far as I can tell.** This is the same Groq key used in the previous two rounds (I was never given a different one in this session). Stating that plainly: it is still un-rotated and has now been used three times and pasted in chat once. Recommend rotating it at console.groq.com.

## Anything else worth flagging
- **Verdict on the fixes:** chunking, vectorizer tuning, context cap and default-model updates all verified working on this machine. Hit-rate numbers reproduce exactly (417 / 11187 / 95%), 6/6 real LLM calls succeeded with no 429s.
- **Remaining quality gaps are now retrieval/agent issues, not infrastructure:**
  1. *Right page, wrong chunk / LLM false negatives* (Mech "established" — answer is in the raw page but the LLM said it wasn't there).
  2. *Wrong page ranks above the department page* for Civil enrolment (academic-programs outranks civil dept) and Electrical M.Tech (civil page ranked first) — TF-IDF limits; embeddings or title/URL boosting remain the likely next step.
  3. *Sub-question decomposition drops the subject* ("when was it announced" → unrelated page) in `agent.py`.
  4. *The `sources` field is the top hit per sub-question, not the pages the LLM actually cited*, so it can list an irrelevant page (Electrical → civil, 5G → convocation) or omit the real one. Consider deriving sources from what the LLM cites or from the chunks actually included in the prompt.
- **Good behavior worth keeping:** in every failure case the LLM said the information wasn't in the passages instead of inventing an answer.
- Server was stopped after testing; port 8000 is free. Server log went to Claude Code's scratchpad, not the project folder.
