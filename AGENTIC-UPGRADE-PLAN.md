# Agentic upgrade plan

Written 30 Oct 2026 after reviewing the repo against published agentic-RAG and university-chatbot designs. Each step is one Claude Code session. Do them in order and stop after each one.

## What the current agent already has

| Pattern from the literature | Status here |
|---|---|
| Router / query classifier | `router.py` handles greeting, thanks, capability, out-of-scope and lookup, but has no topic intents |
| Query rewriting (multi-turn) | `followup.py` |
| Decomposition | `agent.decompose` |
| Hybrid retrieval + reranker | `query.py` |
| ReAct tool loop | `planner.py`, 4 tools, up to 2 rounds |
| Answer verification + one revision | `verifier.py` (deterministic) |
| Visible trace | "How I found this" |

## What is missing, and where the idea comes from

1. **A retrieval grader that acts on its grade (Corrective RAG).** CRAG grades the retrieved passages, and when they look weak it corrects the retrieval *before* answering. Here, the decision is left entirely to the LLM. That's why the planner never opens the T&P page for the placements question. The cross-encoder scores that would show weak retrieval are computed in `query._rerank` and then thrown away.
2. **Asking the student instead of guessing.** AdvisingWise's action set includes "request information from the student", and it keeps a student profile. MARAUS found that most of its remaining errors came from personalisation and vague questions. Here, "what is the hostel fee?" gets a guess drawn from 19 near-identical sheets.
3. **A structured-data tool.** TableRAG keeps tables in a database and answers table questions with a query, not by reading text. MARAUS has a separate calculation agent for numeric questions. Here, fee and calendar tables are already rows (`context | Header: value — ...` lines in `data/raw/doc_*.txt`) but can only be reached by text search.
4. **Handing off to a human.** Commercial university assistants route the questions they can't answer to the right office. Here, a refusal is a dead end.
5. **Topic intents for routing and filtering.** MARAUS's coordinator and the adaptive-RAG classifier tag each query by type before retrieving.
6. **Ablations.** The Agent-Orchestrated Adaptive RAG paper measured reflection *lowering* overall scores and multiplying latency by six. Every agentic piece has to be measured on its own, not assumed to help.

## Rules for every step

- Free tier only: Groq allows 8,000 tokens a minute and about 200,000 a day per model. New logic must be deterministic (no extra LLM call) unless the step says otherwise.
- Don't break what works: the current results are 35/39 on `check_answers.py`, 29/29 on `test_agentic.py`, 29/32 on `chunk_ranks.py`, 15/18 on `fact_ranks.py` and 16/19 on `evaluate.py`. Re-run the no-key checks after every step.
- Add tests for every new behaviour to `test_agentic.py`. They must not need a key.
- Code style: match the existing files. Few comments, only where the reason isn't obvious. Nothing that reads as generated boilerplate.
- Every new decision shows up in `trace` with a plain-English line, so it appears under "How I found this".
- After each step: update EXPERIMENTS-LOG.md (new §21, §22…) with what was measured, plus README/APPLICATION status. Commit with a short message.
- Spot-check end to end with `python check_answers.py --only <name>` instead of the full 45-minute run.

---

## Step 1. Topic intent (foundation, ~1 hour)

`router.py`: add `intent(question) -> str` using keyword rules. The intents are fees, hostel, calendar (exams, classes, registration), scholarship, placement, admission, people (director, dean, registrar, contact, email, phone), department, rules, and other. `respond.answer` returns `intent` and adds it to the trace ("Topic: hostel"). No LLM involved.
Tests: about 15 questions from `check_answers.py` mapped to their expected intents.

## Step 2. Corrective retrieval gate (CRAG-style, ~2 hours, fixes placements)

1. `query._rerank` returns the cross-encoder scores, and `retrieve` / `retrieve_within` put `rerank_score` on each result. The order must stay exactly the same, so no benchmark should move.
2. New `pipeline/grader.py` with `grade(question, report) -> {"grade": "correct"|"ambiguous"|"incorrect", "why": ...}`, based on:
   - the top rerank score of the whole-question results;
   - coverage: whether the question's rare content words (the IDF idea already used in `tools._title_scores`) and any explicit year or programme appear in the top 3 passages.
   Calibrate the thresholds with `chunk_ranks.py` (32 questions with known answer passages). Write the chosen thresholds and the confusion counts into EXPERIMENTS-LOG.
3. In `respond.answer`, before `planner.run`: if the grade isn't "correct", run the corrective action in code without asking the LLM. Run `tools.run_tool("read_document", ...)` on the top 2 entries from `tools.matching_titles` that aren't already among the passages, and add each one's best passage to the evidence. Trace line: "The first search looked weak (reason), so I also looked inside <title>."
4. The planner prompt now gets the grade, so the LLM knows the retrieval was judged weak.

Done when the placements question passes with `--only`, the no-key checks don't drop, and a test pins the gate firing on placements and not firing on the Director question.

## Step 3. Clarify or assume: slot filling and a student profile (~2–3 hours, the most visible in a demo)

1. New `pipeline/slots.py`. It uses `programme_terms.py` to pull `programme`, `year`, `gender`, `category` and `session` out of the question. The required slots depend on the intent: hostel needs programme, year and gender; fees needs programme and category; calendar needs programme, year and session.
2. Clarify only when a required slot is missing **and** the top passages actually disagree on that axis (for example, both B.Tech and M.Tech sheets in the top 7 with different amounts). In that case, return `mode: "clarify"` with a one-line question and 2–4 `choices` taken from the axis values found in the passages. No LLM call, and at most one clarification per question.
3. Student profile: the chat page keeps `{programme, year, gender, category}`, filled from clarification choices and from what the student says ("I'm a first-year B.Tech girl"), and sends it with `/ask`. Add `profile: dict = {}` to the `Question` model in `api/main.py`. Missing slots are filled from the profile, and the answer says so: "Assuming first-year B.Tech (from earlier in this chat)." The profile stays in the browser only; the server never stores it.
4. Chat page: render `choices` as buttons. Clicking one sends it as a follow-up, which `followup.resolve` already handles.
5. Add these cases to `check_answers.py`: "What is the hostel fee?" must clarify; a fully specified hostel question must answer directly; a choice-then-answer conversation must reach ₹32,650.

## Step 4. Hand off to the right office on refusal (~1 hour)

1. Create `data/contacts.json` by hand from `contact_us.txt`, `administrative_officers.txt` and `deans_2026.txt`. Each entry maps an intent to `{office, email, phone, url}`. Copy every value exactly from those files, and give each entry the source URL.
2. When the answer is a refusal (`verifier.is_refusal`) or the verdict is flagged, append "Who can help: <office>, <email>" for the question's intent, with the contact source in `sources`. Add it after verification, labelled as coming from the contacts list, and add a test that every email in contacts.json appears in `data/raw`.

## Step 5. Structured lookup tool for tables (TableRAG-style, ~3 hours, optional if time is short)

1. New `pipeline/build_facts.py`. It parses table-row lines in `data/raw/doc_*.txt` (`<lead-in> | <Header>: <value> — <Header>: <value>; ...`) into SQLite `data/processed/facts.db`, one row per cell. The columns are `doc_id, title, url, date, context, row_label, column, value, number, programme, year, gender, category, session`, with tags from `programme_terms.py`. Add `facts.db` to `.gitignore` and rebuild it like the index.
2. Add tool `lookup_table(keywords, programme?, year?, gender?, category?)`. It runs a **parameterised** query; never let the LLM write SQL. It returns up to 8 rows, each added to `Evidence` as a passage, so citations and the verifier work unchanged. Add it to `tools.SCHEMAS`, plus one prompt line: "For fees, amounts and dated table entries, try lookup_table first."
3. Measure the M.Sc and B.Arch tuition and slot-A mid-sem questions with `--only`. If OCR damage still blocks them, record that honestly in EXPERIMENTS-LOG.

## Step 6. Ablation table for the report (runs across days because of quota)

Add flags so each piece can be switched off: `AGENT_TOOLS=off` (the agent answers from the first search only), `VERIFY_REVISE=off`, `CRAG_GATE=off`, `CLARIFY=off`. Run `check_answers.py` on a fixed 15-question hard subset (the four current failures, the tool-using questions and the follow-ups) for:

| Config | Score | Avg tokens | Avg seconds | Tool calls |
|---|---|---|---|---|
| one-shot | | | | |
| agent, no tools | | | | |
| agent (30 Oct) | | | | |
| + CRAG gate | | | | |
| + clarify/profile | | | | |
| + lookup_table | | | | |

This table is the report's evidence that each agentic piece pays for itself, or an honest note that one doesn't.

## Do not do

- Don't rewrite the system in LangGraph or another framework. `planner.run` already is the ReAct state machine, and a rewrite risks the 35/39 for no gain.
- Don't add extra LLM "agents" (separate grader, judge or critic calls) in the live path. Each one costs tokens the free tier doesn't have, and the literature shows reflection can lower accuracy.
- Don't add web search outside vnit.ac.in.
- Don't store student profiles or IP addresses on the server.
