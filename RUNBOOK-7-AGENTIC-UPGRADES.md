# Runbook 7: agentic upgrades

**For:** Claude Code, running on Shivanand's Windows laptop in `FYP\VNIT-Website-Chatbot\vnit-chatbot`.
**Why:** `AGENTIC-UPGRADE-PLAN.md` compares this agent with published designs: Corrective RAG, MARAUS (university admissions), AdvisingWise (academic advising) and TableRAG. This runbook turns that comparison into exact build steps.
**Owner:** Shivanand directs and is a beginner at app building. Explain anything he must do himself in plain words, one command at a time.

---

## How to use this runbook

Run **one step per Claude Code session**, in order. Paste this, changing the step number:

> Read RUNBOOK-7-AGENTIC-UPGRADES.md, then APPLICATION.md §5–5a and EXPERIMENTS-LOG.md §20. Do **Step N only**, following "Ground rules". Finish with the step's "Done when" checks, write the results into REPORT8.md, commit, and stop.

If a step's "Done when" fails and the step's "If it goes wrong" notes don't fix it, revert that step's files (`git checkout -- <files>`), write what happened in REPORT8.md, and stop. Don't carry a broken step forward.

Steps 0–4 matter most for the demo. Do Step 5 if there's time. Step 6 can run unattended over the following days.

| Step | What | Time | LLM quota |
|---|---|---|---|
| 0 | Freeze a baseline | 15 min | none |
| 1 | Topic intent | 45 min | none |
| 2 | Corrective retrieval gate (CRAG) | 2 h | 2–3 questions |
| 3 | Clarify or assume (slots + profile) | 2–3 h | 3–4 questions |
| 4 | Hand off to the right office | 1 h | 1–2 questions |
| 5 | Table lookup tool (TableRAG) | 3 h | 4–5 questions |
| 6 | Ablations + final numbers | unattended | ~3 days of quota |

---

## Ground rules (every step)

**Environment.** Use the same Python that `start_chatbot.bat` uses. In Git Bash:
```
PY=~/anaconda3/python.exe
cd pipeline
```
The key lives in `~/groq-key.txt`. Load it with `export GENAI_API_KEY=$(cat ~/groq-key.txt)`. Never print, log, echo or commit it, and never put it in a test.

**Don't break what works.** These are the numbers as of 30 Oct 2026 (Step 0 re-measures them):

| Check | Command (from `pipeline/`) | Baseline | Needs key |
|---|---|---|---|
| Agent unit tests | `$PY test_agentic.py` | 29/29 | no |
| Answer passage reaches the LLM | `$PY chunk_ranks.py` | 29/32 | no |
| Answer passage in top 3 | `$PY fact_ranks.py` | 15/18 | no |
| Right page in top 3 | `$PY evaluate.py` | 16/19 | no |
| End to end | `$PY check_answers.py` | 35/39 | yes, ~45 min, ~230k tokens |

After every step, run the four no-key checks. None may drop. Don't run the full `check_answers.py` inside a step, because one run uses more than a day's quota for one model. Use `--only <name-fragment>` (it matches names containing the fragment) with `--pause 30`, and only on the questions the step names.

**Free tier.** Groq allows 8,000 tokens a minute and about 200,000 a day *per model*. The agent uses `openai/gpt-oss-120b`; the fallback and follow-up rewrite use `openai/gpt-oss-20b`. New logic in Steps 1–5 must add **no LLM calls**. It must be code. The only allowed LLM cost is the existing planner using a new tool.

**Code style (Shivanand's preference).**
- Match the existing modules: a module docstring saying *why* the module exists, short functions, plain names.
- No comment on every line, no banner comments, no "Step 1:" comments in code, and no emojis. Comment only where the reason isn't obvious.
- No new dependencies except `sqlite3` (standard library) in Step 5.

**Visible decisions.** Every new decision adds one plain-English line to `trace`, which the chat page shows under "How I found this". Use the existing format: `{"step": "<kind>", "text": "..."}`.

**Tests.** Every new behaviour gets a test in `pipeline/test_agentic.py` that needs no key and no internet. Follow the existing style: plain `def test_...()` functions with `assert`, using the real index where retrieval is involved. Update the "29/29" count wherever docs mention it.

**Docs after every step.**
- `EXPERIMENTS-LOG.md`: a new section (§21 for Step 1, §22 for Step 2, …) covering what changed, what was measured, the before/after numbers, and anything rejected.
- `README.md` "Project status" and "Measured quality", and `APPLICATION.md` §2 and §5a. Keep them true. Stale numbers are worse than none.
- `REPORT8.md`: append a section per step with the commands run, outputs (trimmed) and the "Done when" results.

**Commit after every step**, with a short message in the style of the existing history ("Corrective retrieval gate: grade the first search, look inside the best-titled pages").

---

## Step 0. Freeze a baseline

1. `git status`. Last night's agentic work (planner.py, tools.py, verifier.py, router.py, respond.py, test_agentic.py and the edited files) may still be uncommitted. If so, commit it first: `git add -A && git commit -m "Agentic layer: router, planner with tools, verifier"`. Check that `data/processed/index.pkl`, `chunks.jsonl` and `data/feedback/` are **not** staged (they're in `.gitignore`).
2. Tag it: `git tag before-runbook-7`. Any step can be undone back to here.
3. Back up the index: copy `data/processed/index.pkl` and `chunks.jsonl` to `~/vnit-chatbot-backups/2026-10-30-before-runbook-7/`.
4. Run the four no-key checks and save their summary lines in REPORT8.md under "Baseline".
5. `git push`, and tell Shivanand if push asks for a login.

**Done when:** the working tree is clean, the tag exists, and the four baseline numbers are recorded.

---

## Step 1. Topic intent

**Idea.** MARAUS's coordinator and the adaptive-RAG classifier tag each query by type before retrieving. Steps 3 and 4 need this. Keep it rule-based, which is free and repeatable.

**Build.**
1. In `router.py`, add constants and `intent(question: str) -> str` returning one of: `fees, hostel, calendar, scholarship, placement, admission, people, department, rules, other`.
   - Keyword regexes, checked in a fixed priority order so "hostel fee" is `hostel`, not `fees`: hostel → fees → scholarship → placement → calendar → admission → people → department → rules.
   - `calendar` covers exam, mid-sem, end-sem, classes start, registration, semester, session, convocation and holiday. `people` covers director, dean, registrar, HOD, head, contact, email, phone and helpline. `rules` covers rule book, ordinance, attendance, grading, backlog, re-exam, ragging.
2. In `respond.answer`, compute `topic = router.intent(searched)` for lookups. Add `"intent": topic` to every returned dict (`None` for direct replies). Append the trace line `{"step": "route", "text": f"Topic: {topic}."}` right after the existing route line.

**Tests (add about 15).** Take questions from `check_answers.CHECKS` and assert their intents, e.g. `hostel_fee_*` → hostel, `btech_fee_open` → fees, `director` → people, `dean_academic_email` → people, `placements` → placement, `kotak*` → scholarship, `classes_start*` → calendar. Write one test that loops over a small dict.

**Done when:** test_agentic passes (29 + new), the other three no-key checks are unchanged (this step touches no retrieval), and EXPERIMENTS-LOG §21 is written.

**If it goes wrong:** if a question gets the wrong topic, fix the priority order rather than adding special cases.

---

## Step 2. Corrective retrieval gate (CRAG)

**Idea.** Corrective RAG grades the retrieved passages and fixes the retrieval *before* answering when they look weak. Right now, choosing to open another page is left entirely to the LLM. That's why the planner never opens the T&P page for the 2025-26 placement figures (EXPERIMENTS-LOG §20c), even though `read_document` finds them at rank 1. The cross-encoder already scores every candidate in `query._rerank`, and those scores are thrown away.

**Build.**
1. **Keep the rerank scores** (`query.py`).
   - `_rerank` returns `(ids_in_order, scores_in_that_order)` instead of only ids. Update both callers.
   - `retrieve` and `retrieve_within` add `"rerank": float` to each result dict. When the reranker is disabled, use `None`. Leave `"score"` as it is.
   - The ranking order must not change. Confirm the four no-key checks give **identical** numbers before going on.
   - Check `agent.py` / `generate.select_passages` carry the extra key through. They pass dicts along, so they should, but verify.
2. **New `pipeline/grader.py`** with `grade(question: str, report: dict) -> dict` returning `{"grade": "correct"|"ambiguous"|"incorrect", "top": float|None, "coverage": float, "why": str}`:
   - `top` is the highest `rerank` among the whole-question results in `report` (look at `agent.answer`'s report structure to find them).
   - `coverage` is the share of the question's *rare* content words that appear in the top-3 passages' text. Use word stems (first five letters) and the same IDF-over-titles idea as `tools._title_scores`, or IDF from the TF-IDF vectorizer in the index, whichever is simpler. Count only words with IDF above the median. Also: an explicit academic year in the question (`programme_terms.years`) that appears in none of the top 3 counts as uncovered.
   - Rules: `correct` if `top >= HIGH` and `coverage >= COVER`; `incorrect` if `top < LOW`; otherwise `ambiguous`.
   - **Calibrate HIGH, LOW and COVER from data, not by guessing.** Write `pipeline/grade_calibration.py`, which uses `chunk_ranks.cases()` plus `agent.answer` to record, for each of the 32 answerable questions, `top`, `coverage` and whether the answer passage is within the 7 sent. Print a table. Pick thresholds so that **every question whose answer passage was missed** (including `placements`) grades as not `correct`, while as many as possible of the hits grade `correct`. Put the table and the chosen thresholds in EXPERIMENTS-LOG §22. Also run the 5 must-decline questions through it; they should grade `ambiguous` or `incorrect`.
3. **Corrective action** (`respond.py`, before `planner.run`). Only when `grade != "correct"` and `CRAG_GATE` isn't `off` (env, default on):
   - Take the top 2 entries from `tools._title_scores(searched)` whose URL isn't already among the first-search sources.
   - For each, call `query.retrieve_within(searched, [url], k=2)` and keep the best passage if its `rerank` is above `LOW`.
   - Pass these to the planner as extra first-search passages. Add an optional `extra=None` parameter to `planner.run` and register each with `evidence.add(r, text, origin="corrective")` after the first-search passages, using the same block format.
   - Trace: `{"step": "grade", "text": "The first search looked weak (<why>), so I also looked inside “<title>”."}`. When the grade is correct: `{"step": "grade", "text": "The first search looked relevant (score <top:.1f>)."}`.
   - Tell the planner: add one line to the first user message, `Search quality: <grade> (<why>).`, so the LLM knows the first search was judged weak.
   - The one-shot fallback path should use the extra passages too: append them to what `generate.llm_answer` receives, or leave the fallback unchanged and note that in the docs. Pick whichever is the smaller change.
4. **Budget check.** The extra passages add at most 2 × ~250 tokens. Confirm the first agent prompt for `placements` stays under `planner.PROMPT_BUDGET` (6,000). Print `_estimate_tokens` once while testing, then remove the print.

**Tests.**
- `grade` on the placements question is not `correct`. On `director` it's `correct`.
- With the gate on, the placements question's evidence (call the respond-path pieces with a fake LLM, like the existing planner tests) contains a passage matching `678` before any tool call.
- `_rerank` order is unchanged: compare against the old behaviour on 3 questions, saving ids before the change (a snapshot in the test file is fine).

**Done when:**
- The four no-key checks are not lower (`chunk_ranks` may go **up**; if it uses `agent.answer` only, it won't see the corrective passages, which is fine).
- `$PY check_answers.py --only placements` passes.
- `--only director` and `--only hostel_fee` still pass.
- EXPERIMENTS-LOG §22 has the calibration table.

**If it goes wrong:**
- *Placements still fails, but 678 is in the evidence:* the LLM saw it and didn't use it. Read the saved answer in `answer_check.json` and its trace. Make sure the corrective passage is in the final-answer prompt (`_final_prompt` uses all evidence, so check `FINAL_CONTEXT_CHARS` isn't cutting it off).
- *The gate fires on almost everything:* the thresholds are too strict. Re-read the calibration table. A gate that fires on everything just costs tokens.
- *429s in `--only` runs:* raise `--pause` to 60.

---

## Step 3. Clarify or assume: slots and a student profile

**Idea.** AdvisingWise's agent can "request information from the student" and keeps a student profile. MARAUS found that most of its remaining errors came from personalisation and vague questions. Here, "What is the hostel fee?" gets a guess drawn from 19 near-identical sheets. The agent should ask, show buttons, and then remember the answer.

**Build.**
1. **New `pipeline/slots.py`.**
   - `extract(text) -> dict` returns any of `programme` (via `programme_terms.programmes`, a single value only when exactly one is named), `gender` (`programme_terms.genders`), `category` (new regex: OPEN/General, OBC, SC, ST, EWS, PwD; SC/ST together counts as `sc/st`) and `study_year` (first/1st/second/third/final/fourth year). Keep `study_year` separate from `programme_terms.years`, which handles *academic* years like 2025-26.
   - `REQUIRED = {"hostel": ["programme", "gender"], "fees": ["programme", "category"], "calendar": ["programme"]}`. Other intents need nothing.
   - `needs_clarification(question, intent, passages, profile) -> dict | None`:
     - For each required slot missing from both the question and the profile, read that slot's values from each top passage (the first 7 from `generate.select_passages(report)`).
     - If the passages hold **two or more different values** for it, return `{"slot": s, "question": <one line>, "choices": [{"label": "B.Tech", "value": "btech"}, ...]}` with 2–4 choices, ordered by how often each value appears.
     - If the passages agree, or name nothing, return `None` and just answer. Clarify only when it would actually change the answer. That keeps "Who is the Director?" from ever being asked back.
   - `apply_profile(question, profile) -> (question, note)`: when the question lacks a slot the profile has, append it in words ("What is the hostel fee? (for B.Tech girls)") and return a note "Assuming B.Tech girls, from earlier in this chat." Only fill slots the question's intent requires.
   - `PROFILE_KEYS` and a validator: drop unknown keys and values, so a crafted request can't inject text into the question.
2. **`respond.answer`** gets a new parameter `profile=None`. Order:
   resolve follow-up → route → intent → `apply_profile` (trace the note, set `understood_as`) → first search → **clarify check** (unless `CLARIFY=off`) → CRAG gate → planner.
   On clarification, return immediately with `mode: "clarify"`, `answer` = the clarifying question, `clarify` = the dict above, `sources: []`, `verification: None`, plus a trace line: "Your question fits several different documents (B.Tech, M.Tech) with different answers, so I asked which one you mean." No LLM call. At most one clarification per question: if `history` shows the previous turn was a clarification for the same slot, never clarify again.
3. **`api/main.py`:** add `profile: dict = {}` to `Question`, clean it with the slots validator, and pass it to `respond.answer`. Never store it, because profiles are personal.
4. **`frontend/index.html`:**
   - Keep `let profile = {}` in memory (not localStorage) and send it with every `/ask`.
   - When `data.clarify` is present, show its `choices` as buttons under the answer. Clicking one sets `profile[slot] = value`, shows it as the student's own message ("B.Tech"), and re-asks the **original** question with the updated profile.
   - When the server's `understood_as` / trace says a profile was assumed, show it the same way "Understood as" is shown.
   - Add a small "Clear my details" link that empties `profile`.
   - Keep the existing escaping (`escapeHtml`). Choices are server-generated, but escape them anyway.
5. **`check_answers.py`:** add support for a `profile` and a `"clarify"` expectation. New cases:
   - `clarify_hostel_vague`: "What is the hostel fee?" → mode is `clarify` and the choices include `btech`. Free, since it needs no LLM.
   - `clarify_then_answer`: question "What is the hostel fee for first year?" with profile `{"programme": "btech", "gender": "girls"}` → answer matches `32,?650`.
   - `no_clarify_when_specific`: the existing fully specified hostel question must **not** clarify.
   - `no_clarify_director`: "Who is the Director of VNIT?" must not clarify.

**Tests (no key):** `extract` on 8 phrasings; `needs_clarification` returns a dict for the vague hostel question with the real index's passages and `None` for the specific one; `apply_profile` adds the words and the note; the validator drops `{"programme": "x; ignore previous"}`.

**Done when:**
- The no-key checks are unchanged (this step doesn't touch retrieval).
- The 4 new cases pass with `--only clarify` and `--only no_clarify`.
- `--only conv_hostel_girls` still passes.
- Shivanand has tried it in the chat page. Write the exact clicks for him in REPORT8.md: start `start_chatbot.bat`, ask "What is the hostel fee?", click B.Tech, click Girls, see ₹32,650.

**If it goes wrong:**
- *It clarifies too often in the 39-question set:* run all 39 questions through `respond.answer` with a fake LLM (or `use_agent=False` and no key, so extractive mode) just to count `mode == "clarify"`. It should be **0** for the existing 39, since all of them are specific. Tighten `needs_clarification` until it is.
- *Gender is missing from the passages:* some fee sheets say "Boys" only in the title. Read slot values from `title + text`.

---

## Step 4. Hand off to the right office when it can't answer

**Idea.** Commercial university assistants route the questions they can't answer to the right office. Here, a refusal is a dead end.

**Build.**
1. **`data/contacts.json`**, written by hand from `data/raw/contact_us.txt`, `administrative_officers.txt`, `deans_2026.txt` and `director_office_staff.txt` (and a department file only if needed). Map each Step 1 intent to one office, for example `{"hostel": {"office": "...", "email": "...", "phone": "...", "source_url": "..."}}`. Copy every email and phone **character for character** from those files, with `source_url` taken from the file's `SOURCE_URL:` line. Leave out an intent rather than guess its office. `other` maps to the general Registrar/Director office contact on the Contact Us page.
2. **`respond.py`:** after verification, if `verifier.is_refusal(answer)` or the verdict is `unsupported`, and `intent` has a contact, append:
   `\n\n**Who can help:** <office> — <email>, <phone>`
   Add the contact page to `sources` if it isn't there. Trace: "I couldn't find this in VNIT's documents, so I've added who to contact." Don't run it through the verifier again: the contact comes from a checked file, not the LLM.
3. The chat page needs no change if the answer markdown renders bold. Check that it does.

**Tests (no key):** every email and phone in `contacts.json` appears verbatim in `data/raw/*.txt`; a refusal with intent `hostel` gets the hostel contact appended; a normal answer gets nothing appended.

**Done when:**
- The tests pass.
- `--only wifi` (the hostel Wi-Fi must-decline case) still passes. Check the refusal pattern still matches with the contact line appended; if not, put the contact in a separate `handoff` field and show it in the page instead of inside `answer`.
- The no-key checks are unchanged.

---

## Step 5. Table lookup tool (TableRAG-style), optional

**Idea.** TableRAG keeps document tables in a database and answers table questions with a query; MARAUS gives numeric questions their own agent. Docling already turned every table row into a line of `data/raw/doc_*.txt`. This step puts those rows in SQLite and gives the agent a tool for them. The point is a second kind of tool, structured lookup, alongside text search.

**Build.**
1. **Look before parsing.** Pull 40 real table lines: `grep -h " | " ../data/raw/doc_*.txt | grep -iE "fee|rs\.|exam|date" | head -40`. Write the parser for what's actually there. The known format is `<lead-in> | <Header>: <value> — <Header>: <value>`, with sub-columns joined by `; `, but check it.
2. **New `pipeline/build_facts.py`.** It builds `data/processed/facts.db` with one table:
   `facts(id, doc_url, title, date, lead_in, row_label, column, value, number, programme, gender, category, study_year, academic_year)`
   - One row per cell. `number` is the value parsed as a number (handle "1,25,000", "Rs. 32650/-" and "Nil" as 0), otherwise NULL.
   - Tag columns come from `slots.extract` / `programme_terms` applied to `title + lead_in + row_label`.
   - Rebuild it like the index: run after `chunk.py` / `build_index.py`. Add `facts.db` to `.gitignore`, and add the command to HOW-TO-RUN §5.
   - Print counts per document type at the end.
3. **Tool `lookup_table`** in `tools.py`:
   - Arguments: `keywords` (required), plus optional `programme`, `gender`, `category`, `study_year`, `academic_year`.
   - Run a **parameterised** query: tag filters as `=` on columns; keywords as `LIKE` on `lead_in || row_label || column || title`, scored by how many keywords match.
   - Never let the LLM write SQL.
   - Return up to 8 rows, newest documents first.
   - Turn each row into a result dict (`text` = `"<lead_in> | <row_label> | <column>: <value>"`, `title`, `source_url`, `fetched` = date) and register it through `evidence.render`. The rows become `[P#]` passages, so citations and the verifier work unchanged.
   - Add it to `SCHEMAS`, with a description saying it's for fee amounts and dated table entries.
4. **Planner prompt:** one line, "For fee amounts and dates that come from tables, try lookup_table before searching again."

**Tests (no key):** the parser on 6 real lines copied from `data/raw` (including a fee row and a calendar row); `lookup_table` for B.Tech hostel girls returns a row containing 32650; a SQL-ish keyword (`"'; DROP TABLE facts; --"`) returns no rows and raises nothing.

**Done when:**
- The tests pass and the no-key checks are unchanged.
- `--only msc`, `--only barch` and `--only slot_a` have been run, with the outcome recorded **honestly**. If OCR damage still blocks M.Sc/B.Arch, say so, and paste the table lines that show why.
- `--only hostel_fee` and `--only btech_fee` still pass.

**If it goes wrong:** if the agent never calls `lookup_table`, check its description and prompt line first. Don't force it by code; Step 2's gate is the deterministic part.

---

## Step 6. Ablations and final numbers (runs over several days)

**Idea.** The Agent-Orchestrated Adaptive RAG paper measured reflection *lowering* overall scores and multiplying latency by six. The report has to show what each piece does here, measured.

1. **Switches.** Add env flags (default on) and make sure each one fully disables its piece:
   - `AGENT_TOOLS=off`: the planner gets no tools and answers from the first search;
   - `VERIFY_REVISE=off`: verify and badge, but no revision call;
   - `CRAG_GATE=off`, `CLARIFY=off`, `LOOKUP_TABLE=off` (removes the tool from `SCHEMAS`).
2. **Hard subset.** Add `--set hard` to `check_answers.py`: placements, msc, barch, slot_a, summer_term, hostel_fee_girls, the tool-using questions from `answer_check.json` (`usage.tool_calls > 0`), both conversations, two must-decline questions and the new clarify cases. Aim for about 15. Give each configuration its own results file (`answer_check_<config>.json`).
3. **Configurations** (one per quota window; the agent's model gets about 3 full hard-set runs a day):

| Config | Flags |
|---|---|
| one-shot | `--pipeline oneshot` |
| agent, no tools | `AGENT_TOOLS=off CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off` |
| agent (30 Oct) | `CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off` |
| + CRAG gate | `CLARIFY=off LOOKUP_TABLE=off` |
| + clarify | `LOOKUP_TABLE=off` |
| full | none |

4. **`pipeline/ablation_table.py`** reads the results files and prints one markdown table: score, must-decline refused, average tokens, average seconds, average tool calls, gate fired, clarifications. Paste it into EXPERIMENTS-LOG, README "Measured quality" and APPLICATION §6.
5. **Then one full 39+ run** of the full configuration (`check_answers.py`, finishing with `--resume` the next day if the quota runs out). This becomes the headline number.
6. **Finish the one-shot baseline** if it's still incomplete: `check_answers.py --pipeline oneshot --resume`.

**Done when:** the table exists with every row filled, the headline number is updated everywhere, and REPORT8.md ends with a short summary of what each piece contributed, including any piece that didn't help.

---

## Don't do

- Don't rewrite in LangGraph, CrewAI or any framework. `planner.run` already is the ReAct loop, and a rewrite risks the measured 35/39.
- Don't add LLM calls for grading, judging or critiquing in the live path. The free tier can't afford them, and the evidence says they don't reliably help.
- Don't add web search beyond vnit.ac.in, or store profiles or IP addresses on the server.
- Don't hand-edit results files. Re-score with `check_answers.py --rescore` if a pattern changes, and record why.
- Don't change the "never pressure the model to answer" prompt rules (APPLICATION §7).

## After all steps: tell Shivanand

In plain words, in REPORT8.md and in the final message:
1. The new demo moves:
   - ask "What is the hostel fee?" and click through the buttons;
   - ask the placements question and open "How I found this" to see the corrective step;
   - ask the Wi-Fi password and see "Who can help".
2. Which slides change (10 "How agentic it is", 16–19 numbers), with the new numbers.
3. That `git push` is needed, and the exact command.
