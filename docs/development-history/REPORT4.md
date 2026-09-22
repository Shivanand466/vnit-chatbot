# Sources-field and decomposition fixes verification

Run on: 2026-09-21 (Windows 11, Git Bash + Anaconda Python 3.13.5, via Claude Code). No project code or data was modified this round. `pipeline/agent.py` and `pipeline/generate.py` were confirmed updated (top-3 chunks per sub-question in `generate.py`); `data/raw/` still 79 files and `data/processed/` not rebuilt, as the runbook said. Same Groq key as the previous rounds (still not rotated to my knowledge), default model `openai/gpt-oss-20b` (no `GENAI_MODEL` set).

**Short version:** the two code fixes work as designed (`sources` now reflects the prompt; the 5G sub-question no longer loses its subject). But neither of the two remaining "not found" answers is fixed, and I measured why: in both cases the chunk containing the answer ranks below the top-3 cutoff.

Question: "What specializations does the Electrical Engineering M.Tech offer?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/engineering/civil/`, `https://vnit.ac.in/academic-programs`, `https://vnit.ac.in/engineering/electrical/`
  answer: "The M.Tech programmes in Electrical Engineering available at VNIT Nagpur are listed under the Academic Programs page and include: **Integrated Power System** [Academic Programs — https://vnit.ac.in/academic-programs] and **Power Electronics** [Academic Programs — https://vnit.ac.in/academic-programs]. These are the only Electrical Engineering-focused M.Tech specializations mentioned in the provided passages."
  Fixed vs REPORT3.md?: **Partially (mostly yes).** `sources` now lists what was actually in the prompt, and the electrical department page appears (at rank 3, as Cowork diagnosed) instead of being dropped. The answer contains the right facts. Remaining nits: (a) civil is still ranked first, so a civil page is listed among the sources for an electrical question (it is honest — it was in the prompt — but it is noise); (b) the answer says "Power Electronics" whereas the department page says "Power Electronics and Drives (PED)" — the LLM cited the Academic Programs page's shortened wording rather than the electrical dept page, even though that page was in the prompt.

Question: "How many undergraduate students does Civil Engineering enroll annually?"
  mode: `llm (openai/gpt-oss-20b)`
  sources: `https://vnit.ac.in/academic-programs`, `https://vnit.ac.in/ongoing-research-collaborations`, `https://vnit.ac.in/engineering/civil/`
  answer: "The passages provided do not contain information about the number of undergraduate students Civil Engineering enrolls annually." followed by a list of the three sources consulted.
  Fixed vs REPORT3.md?: **Partially.** `sources` is now honest and includes the civil department page (a real fix vs REPORT3, where it was absent). But the answer is still "not found", because the civil page's chunk that reached the LLM was the wrong one. Measured: the civil chunk in the top-3 has no "intake" sentence; the chunk with "It has an intake of 120 students per year under UG Course and 100 per year under PG Courses" (`civil_department::1`) ranks **12th** for this question, far outside top-3. So the page-level ranking is fixed, but chunk-level ranking still buries the answer. The LLM again hedged honestly rather than guessing.

Question: "Tell me about the 5G lab and when was it announced"
  mode: `llm (openai/gpt-oss-20b)`
  sub-questions now: ["Tell me about the 5G lab", "when was the 5G lab announced"]  (decomposition fix confirmed working in the live API)
  sources: `https://vnit.ac.in/5g-lab-vnit-nagpur` (only; the unrelated convocation page is gone)
  answer: A detailed bulleted description of the lab (advanced hardware/software for 5G, IoT, edge computing; 5G core and radio; IoT, edge/MEC, AR/VR/MR, smart surveillance applications; hands-on platform for students, faculty and industry; access to 5G test setups for startups and MSMEs), each bullet cited to "5G Lab VNIT Nagpur". Then: "**Announcement date** — The passages provided do not mention when the 5G lab was announced."
  Found the announcement date this time?: **No.** As Cowork predicted. I measured it: for "when was the 5G lab announced", the two chunks containing "October 27" / "announcement was made" rank **4th and 9th**; the top three are three *other* sections of the same 5G page (identical top-3 for both sub-questions), so all the retrieved passages are on-topic but none has the date.

Any errors this round: **None.** All three returned `llm (openai/gpt-oss-20b)`, no 429s, no extractive fallbacks.

## Anything else worth flagging
- **Verdict:** both fixes verified. `sources` = what was in the prompt (Electrical and Civil now include the right department page; 5G no longer lists an irrelevant page). Decomposition keeps the subject ("when was the 5G lab announced").
- **What's left is chunk-level ranking, not page-level.** Measured ranks (k=15) of the answer-bearing chunk: Civil intake = 12; 5G announcement date = 4 (and 9). Raising `[:3]` to `[:5]` would fix the 5G case and cost roughly 2 more chunks of context per sub-question (the `MAX_CONTEXT_CHARS` ceiling is the guard against 429s), but would not fix Civil (rank 12). Civil needs better ranking rather than more context — e.g. weighting the page title/URL match ("Civil Engineering") into the chunk score, or real embeddings.
- **The `sources` list doesn't dedupe by relevance:** it lists every page in the prompt, so an answer drawn from one page can still show two or three other pages beside it (Electrical answer cites only Academic Programs but sources shows civil, academic-programs and electrical). Correct by construction now, but a reader can't tell which page supports the claim. Optional improvement: only list pages the LLM actually cited in its answer text (it already writes "[Title — URL]" citations).
- The LLM continues to hedge instead of inventing when the answer isn't in the prompt (all three "not found" cases this round).
- Server stopped, port 8000 free; server log kept in Claude Code's scratchpad, not the project.
