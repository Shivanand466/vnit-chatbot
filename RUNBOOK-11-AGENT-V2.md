# Runbook 11: Agent v2, a chatbot that works like Claude or ChatGPT

**For:** Claude Code, running unattended overnight on Shivanand's Windows laptop (VS Code extension), opened on the folder `FYP\VNIT-Website-Chatbot\` (the parent folder, not `vnit-chatbot`).
**Goal:** the VNIT Assistant should feel and behave like Claude or ChatGPT:
- it streams its answer word by word, and shows what it's doing while it works ("Searching VNIT documents…", "Opening: Fee notice S-27…");
- it remembers the whole conversation, not just the last 3 questions;
- it plans and takes as many steps as a question needs, not at most 2 rounds;
- it has more tools (latest notices, open a live vnit.ac.in page, today's date, office contacts);
- it does more kinds of task: compare, summarise a document, explain a procedure step by step, draft an email or application to an office, answer in Hindi or Marathi when asked in them;
- its chat page has the usual controls: stop, regenerate, copy, edit the last question, suggested follow-ups, new chat.

It still answers VNIT facts **only from VNIT's documents, with sources, and checks every figure**. That's the project's point, and what Claude or ChatGPT can't promise about VNIT.

**Be honest in the report about one thing:** the model is still Groq's free `openai/gpt-oss-120b`, not Claude or GPT. What becomes "like Claude or ChatGPT" is the agent around it: memory, planning, tools, streaming and the interface.

**Owner:** Shivanand directs and is a beginner at app building. He is asleep. In the morning he reads the "Good morning" section of `vnit-chatbot-v2/REPORT11.md`.

---

## The one thing that must not break: the ablations

Since 20 Nov 18:28, `run_ablations.sh` has been measuring the **frozen** chatbot (tag `final-index-2026-11-20`) in a window called "VNIT ablations", for the report. It runs from `vnit-chatbot/` and starts Python afresh every time it resumes, so **any change to files in `vnit-chatbot/` would change what it measures**. Therefore:

- **All v2 work happens in a separate git worktree, `VNIT-Website-Chatbot/vnit-chatbot-v2/`, on a new branch `agent-v2`.** Nothing in `vnit-chatbot/` is edited, built, committed, checked out or reset tonight. Not one file.
- Don't stop, restart or touch the ablation runner, its window, its log or its results.
- **Groq quota belongs to the ablations.** They use `openai/gpt-oss-120b` and `openai/gpt-oss-20b`, and each model has its own daily allowance. Tonight, v2 makes **no live calls on those two models**. Live testing tonight uses only a different Groq model, if one is available (Step 0 finds out), with its own allowance. Everything else is tested with a fake LLM.
- Merging v2 into `main` is **Shivanand's decision after the ablations finish** and after v2 has run the full 105-case check (Step 10 writes the plan). Tonight ends with v2 on its own branch, runnable side by side with v1.

---

## How this runbook is run

One Claude Code session, started with:

> Read RUNBOOK-11-AGENT-V2.md and vnit-chatbot-v2/PROGRESS-11.md (if it exists). Do every step from the first one not marked through Step 10, in order, without stopping between steps, following "Ground rules". After each step: run its "Done when" checks, write the results into vnit-chatbot-v2/REPORT11.md, mark the step in PROGRESS-11.md, and commit on branch agent-v2. Never ask a question.

| Step | What | Rough time |
|---|---|---|
| 0 | Worktree, branch, frozen index, dev model, baseline | 30 min |
| 1 | Conversation memory | 1 h |
| 2 | The agent loop v2: plan, act, observe, repeat | 2 h |
| 3 | New tools | 1.5 h |
| 4 | More kinds of task | 1.5 h |
| 5 | Hindi, Marathi and Hinglish | 45 min |
| 6 | Streaming API | 1.5 h |
| 7 | The chat page, like Claude or ChatGPT | 2 h |
| 8 | The website widget gets the same | 1 h |
| 9 | Tests and measurements | 1.5 h |
| 10 | Docs, the merge plan and the morning report | 45 min |

The times add up to more than one night. **Steps 1, 2, 6 and 7 matter most** for the "like Claude or ChatGPT" feel. If time runs short, do 8 and 5 last, and timebox any step at 1.5× its estimate: finish the smallest working version, record what's missing, and move on.

---

## Ground rules (every step)

**Never stop to ask.** Decide, record under "Decisions" in PROGRESS-11.md with one line of reasoning, and carry on. A step that fails reverts its own files in the worktree, is marked `FAILED` with the reason, and the run moves on.

**Where.**
- Code: `vnit-chatbot-v2/` (worktree, branch `agent-v2`).
- Website widget: `vnit-website/`, on a new branch `agent-v2` (Step 8 only). Its `master` stays as it is.
- Read-only: `vnit-chatbot/` (all of it), the ablation runner, `~/vnit-chatbot-backups/`.

**Python and keys.** `PY=~/anaconda3/python.exe`. The Groq key is loaded only inside a command that needs it, `GENAI_API_KEY=$(cat ~/groq-key.txt) ...`, and only for the dev model (Step 0). Never print, echo, log, commit or Read-tool it. The Drive key isn't needed tonight.

**v1 stays available inside v2.** Every v2 behaviour is behind a switch, default **on in v2**, so `AGENT_V2=off` gives exactly v1's behaviour on the same branch. That's what makes v1 versus v2 a fair comparison for the report (one more ablation row). Test that `AGENT_V2=off` passes all of v1's tests unchanged.

**Facts only from VNIT's documents.** New task types (drafting, explaining, summarising, general questions) may write freely around the facts, but every VNIT figure, date, name, email and phone number still comes from a passage and passes the verifier. The must-decline cases (Wi-Fi password, JoSAA ranks, GATE cut-offs, a warden's address, old fees) must still be declined. **This is the one rule a ChatGPT-like feature must never weaken.**

**Free tier limits are real.** 8,000 tokens a minute and about 200,000 a day per model. A Claude-like loop that takes 8 steps would cost 40k tokens and 5 minutes a question. So v2 has a per-question token budget (`AGENT_V2_BUDGET`, default 14,000), and the agent is told how much budget is left at every step. Streaming the steps live (Step 6) is what makes a 30–60 second answer feel acceptable.

**No new dependencies.** Standard library plus what's already installed (FastAPI, uvicorn, requests, BeautifulSoup). Streaming uses FastAPI's `StreamingResponse` with Server-Sent Events. The chat page uses plain JS (`fetch` with a stream reader, `AbortController`). No frameworks, no CDNs.

**Code style (Shivanand's preference).** A docstring saying *why* in each module, short functions, plain names, comments only where the reason isn't obvious, no banner or "Step N" comments, no emojis in code.

**Tests.** Every new behaviour gets a no-key, no-internet test in `pipeline/test_agentic.py` (or a new `pipeline/test_agent_v2.py` that `test_agentic.py` also runs), using a **fake LLM** that returns scripted replies, including tool calls. Live-page fetching is tested against a saved HTML file, not the internet.

**Ports.** v2 test servers use port **8020** and are stopped before the step ends. Never 8000 (Shivanand's v1) or 8010. The morning launcher for v2 uses **8001**.

**Git.** Commit after every step on `agent-v2`. Stage by name or folder. Never commit `index.pkl`, `chunks.jsonl` or `facts.db`. Never push, never merge, never touch `main`.

---

## Step 0. Worktree, branch, frozen index, dev model, baseline

1. Record that the ablations are running: `tail -3 vnit-chatbot/data/processed/ablation_runs.log` and the process list. Don't touch them.
2. Create the worktree **from the frozen tag**:
   `git -C vnit-chatbot worktree add ../vnit-chatbot-v2 -b agent-v2 final-index-2026-11-20`.
   (This adds a branch and a worktree entry inside `vnit-chatbot/.git`, but doesn't change any file in `vnit-chatbot/`'s working tree. Confirm with `git -C vnit-chatbot status --short` before and after: identical.)
   Then bring the worktree up to `main`'s latest commit, `ddcb7cd` (docs only after the tag): `git -C vnit-chatbot-v2 merge --ff-only ddcb7cd`, if that fast-forwards; otherwise stay on the tag and record why.
3. Copy the frozen index into the worktree (it isn't in git): from `~/vnit-chatbot-backups/final-index-2026-11-20/` copy `index.pkl`, `chunks.jsonl`, `facts.db` to `vnit-chatbot-v2/data/processed/`. Check sizes. Copy `RUNBOOK-11-AGENT-V2.md` into the worktree and commit it.
4. `data/feedback/` and `data/raw_*held*` folders aren't in git. Don't copy feedback (students' data). Create an empty `data/feedback/`.
5. **Find a dev model.** With the key loaded inline, `GET https://api.groq.com/openai/v1/models` and list model ids (print ids only, never headers). Pick one that is **not** `openai/gpt-oss-120b` or `openai/gpt-oss-20b`, supports tool calling, and is a strong general model. Prefer, in order, whatever of these exist: `moonshotai/kimi-k2-instruct*`, `qwen/qwen3-32b`, `llama-3.3-70b-versatile`, `meta-llama/llama-4-*`. Record it as `DEV_MODEL` in PROGRESS-11. Make one tiny test call (a 20-token reply) to confirm it works and has allowance. **If none works, there is no live testing tonight**: every step uses the fake LLM, and Step 9 writes the live tests as commands for later.
6. Baseline in the worktree, no key: `test_agentic.py`, `chunk_ranks.py`, `fact_ranks.py`, `evaluate.py`, `evidence_check.py`. They must equal REPORT10's numbers (73/73, 78/82, 13/18, 16/19, 80/82 + 11/11), since it's the same code and index. Record them.

**Done when:** the worktree is on `agent-v2` with the frozen index, `vnit-chatbot/`'s status is unchanged, the dev model (or "none") is recorded, and the baseline equals REPORT10.

---

## Step 1. Conversation memory

**Now:** the page sends only earlier *questions*, and the server keeps the last 3 (`MAX_HISTORY`), used only to rewrite a follow-up. **Like Claude/ChatGPT:** the assistant knows what it said before.

1. **API:** `/ask` accepts `turns: [{"q": "...", "a": "..."}]` as well as the old `history` (keep `history` working for v1 and `check_answers.py`). The server keeps the last **6** turns, trims each answer to 600 characters, drops source lists and traces, and caps the whole block at about 1,500 tokens (oldest turns dropped first). It still stores nothing.
2. **Follow-ups:** `followup.resolve` keeps its code fast path. The LLM rewrite gets the question-and-answer turns, so "how do I pay it?" after a fee answer becomes "How do I pay the B.Tech tuition fee for Winter 2026?". "Which of those is cheaper?" and "the second one" must work.
3. **The agent sees the conversation:** the planner's first message gets a short "Conversation so far" block (the trimmed turns), so it can answer "and when is it due?" or "summarise what you told me" without searching again when the earlier answer already holds it. Facts it reuses must still come from passages: earlier answers count as context, **not** as evidence for the verifier. If the agent reuses a figure, it must cite the source again (search for it again if needed).
4. **Profile** (programme, gender, …) still lives only in the page and works as now.

**Tests (fake LLM):** 6 turns kept and 7 trimmed to 6; the token cap drops the oldest; "how do I pay it?" with a fee turn is rewritten to include the programme; earlier answers never count as verifier evidence; `AGENT_V2=off` gives v1's exact behaviour.

**Done when:** tests pass; the no-key checks equal the baseline. Commit.

---

## Step 2. The agent loop v2: plan, act, observe, repeat

**Now:** `planner.run` allows `MAX_TOOL_ROUNDS = 2` rounds of at most 2 calls each, then must answer. **Like Claude/ChatGPT:** the agent keeps going until it has what it needs, within a budget, and can do several things at once.

Build `pipeline/agent_loop.py` (v2), reusing `planner.py`'s pieces (the client, the rate pacer, `Evidence`, `_final_prompt`, the verifier step). Don't fork them; import them.

1. **Plan first, out loud and short.** The first reply may contain a short plan (1–4 bullets: "1. Find the S-27 fee notice. 2. Look up the hostel fee row. 3. Add them.") before tool calls. Show the plan as a trace line `{"step": "plan", ...}`. Multi-part questions ("fee for B.Tech and B.Arch, and when is it due?") get one bullet per part, and the loop tracks which are done.
2. **Loop:** up to `AGENT_V2_MAX_STEPS` (default 6) tool rounds, up to 3 calls per round run in **parallel** (a thread pool; the tools are read-only), stopping when:
   - the model answers without calling a tool;
   - every plan part is marked done;
   - the token budget (`AGENT_V2_BUDGET`, default 14,000, counted with the existing `_estimate_tokens` and actual usage) would be passed by another round;
   - or two rounds in a row add no new evidence (stuck).
   Each round's prompt says how many steps and tokens are left.
3. **Reflection, done by code, not an extra LLM call.** After each round, the loop checks what the round found: new passages? Do they contain a figure or date of the kind asked for (the `grader`/`verifier` helpers)? It tells the model in one line ("That search found nothing new about the due date; try the fee notice itself."). This is what makes it persistent like Claude, without paying for a critic model.
4. **Answer and verify** as now: `_final_prompt` over all evidence, the verifier, one revision if needed, and the "Who can help" hand-off.
5. **Context control.** Evidence passages shown to the model are capped. When the evidence would pass `PROMPT_BUDGET`, keep the passages already cited in the plan's done parts plus the best-ranked rest, and tell the model which ones were set aside (by title) so it can reopen one.
6. Keep the free-tier behaviour: the rate pacer waits for the per-minute limit, and the existing fallback (one-shot, then extractive) still applies when the model fails.

**Tests (fake LLM, scripted):** a 4-round run with parallel calls; stopping on budget; stopping when stuck; plan parts tracked and the stop when all are done; the reflection line appears when a round adds nothing; the verifier still runs; `AGENT_V2=off` uses `planner.run` unchanged.

**Done when:** tests pass; the no-key checks equal the baseline (retrieval is unchanged); with the dev model (if any), 3 live multi-part questions are answered and their traces recorded (tokens, steps, seconds). Commit.

---

## Step 3. New tools

Add to `tools.py` (in the worktree), each with a schema description written for the model, each registered through `Evidence`, so results become `[P#]` passages the verifier can check:

1. **`latest_notices(category?, n?)`:** the newest documents from `data/documents/inventory.json` plus `status.json` (converted and not excluded), filtered by category (fees, academics, hostel, scholarship, placement, admission, recruitment), as passages with title, date and link. For "any new notice about fees?" and "what's the latest on scholarships?".
2. **`fetch_vnit_page(url)`:** open a **live** page, **only** on `vnit.ac.in` (and its sub-sites), through the existing `fetch_utils` (robots.txt, user agent, 1 request a second), 10 s timeout, text capped at 2,500 characters, with a 24-hour on-disk cache in `data/cache/pages/` (in `.gitignore`). Trace: "Opened the live page …". For "is the latest notice still on the website?" and pages the crawl missed. Any other host is refused with a plain message. Fall back to the crawled copy when offline. Switch: `LIVE_PAGES=off`.
3. **`today()`:** today's date in IST, so the agent can answer "is the fee deadline over?" and "when is the next holiday?". (A date comes from code, not a passage, so mark it as trusted for the verifier.)
4. **`contact_office(topic)`:** the office from `data/contacts.json` for a topic. The hand-off already uses it; now the agent can choose it mid-answer ("who do I email about a refund?").
5. Update the planner prompt with one line per tool on when to use it. Keep the tool list short in the prompt (descriptions under 25 words) to save tokens.

**Tests (no internet):** `latest_notices` order and category filter on the real inventory; `fetch_vnit_page` refuses `google.com` and `vnit.ac.in.evil.com`, parses a saved HTML fixture, and uses the cache; `today()` format; `contact_office` returns the hostel office for "hostel"; each tool's result gets a `[P#]` passage.

**Done when:** tests pass; the no-key checks equal the baseline; live (dev model, if any): "any new fee notice?" uses `latest_notices`, "is the Summer 2027 fee deadline over?" uses `today` plus a fee passage. Commit.

---

## Step 4. More kinds of task

Extend `router.py` with **task types** (code rules first, as Runbook 7 Step 1 did for topics): `lookup` (today's behaviour), `compare`, `summarise`, `explain` (a procedure, step by step), `draft` (an email or application), `general` and `chat`. Add a trace line, "Task: compare.", and give the planner one task-specific instruction line:

- **compare:** "fees for B.Tech vs B.Arch", "which hostel is cheaper". The answer is a small markdown table, one row per item, every cell cited. Plan one part per item.
- **summarise:** "summarise the hostel rules", "what does the S-27 fee notice say?". Find the document (`find_documents`), read its passages in order (`read_document`, more than one call if needed), then write 5–8 bullets with citations.
- **explain:** "how do I apply for fee remission?", "steps to get a bonafide certificate". Numbered steps, each from a passage, plus the office contact at the end.
- **draft:** "write an email to the hostel warden asking for a fee extension". The letter itself is written freely (polite, short, with `[Your name]`, `[Roll number]` placeholders), but any VNIT fact in it (an office email, a deadline, a fee) comes from passages and is verified. The office's email comes from `contact_office`. Mark the draft clearly: "Draft — check before sending."
- **general:** a general concept question that isn't about VNIT ("what is CGPA?", "what does DASA mean?"). Answer briefly from general knowledge, **clearly labelled** "General answer, not from VNIT's documents", and **with no VNIT-specific figures, dates, ranks or names**. If the question asks for anything VNIT-specific or time-sensitive (fees, ranks, cut-offs, dates, people), it isn't `general`: it goes through `lookup`, and is declined if not found. The verifier flags any figure in a general answer. **All 10 must-decline cases must still decline; test that in the no-key path (task type and route).**
- **chat:** greetings and thanks, as now (no search, no cost), plus "what can you do?" listing the new abilities.

**Tests:** about 25 phrasings mapped to task types (in a dict, one looping test); the must-decline questions are never `general`; a draft with a fake LLM gets the office email from `contact_office` and the verifier checks it; a compare answer with a fake LLM renders as a table.

**Done when:** tests pass; the no-key checks equal the baseline; live (dev model): one of each task type answered, the outputs pasted (trimmed) into REPORT11. Commit.

---

## Step 5. Hindi, Marathi and Hinglish

1. Detect the question's language in code: Devanagari script means Hindi or Marathi (tell them apart with a small list of common words in each), and Latin-script Hindi ("hostel ki fees kitni hai") is Hinglish, detected by common words (`kitni`, `kya`, `hai`, `kab`, `kaise`).
2. The **search runs in English**: the planner's first instruction says "the student wrote in Hindi; search with English keywords" (no extra LLM call: the planner writes the English search itself; also add the original question's numbers and programme names to the first search, which `programme_terms` can already read).
3. The **answer is written in the student's language**, with numbers, fee amounts, dates and emails kept exactly as in the sources (so the verifier still matches them). Source titles stay as they are.
4. `general`/`chat` replies in the same language too.

**Tests (fake LLM):** detection on 9 phrasings (3 each); the first search for a Hinglish hostel question contains `hostel` and `fee`; numbers in a Hindi answer pass the verifier.

**Done when:** tests pass; live (dev model): one Hindi, one Marathi and one Hinglish question answered correctly, outputs recorded. Commit.

---

## Step 6. Streaming API

**Like Claude/ChatGPT:** the answer appears word by word, and the steps appear as they happen.

1. New endpoint `POST /ask/stream`, same body as `/ask`, returning **Server-Sent Events** (`text/event-stream`):
   - `event: step`: each trace line, as it happens (plan, search, "Opening: …", grade, tool results);
   - `event: token`: pieces of the final answer as the LLM writes it (Groq supports `"stream": true` on the OpenAI-compatible API; read the `data:` lines and pass the `delta.content` pieces on);
   - `event: replace`: when the verifier makes the answer be revised, the full revised text (the page swaps it in);
   - `event: done`: the full JSON exactly as `/ask` returns it (sources, verification, mode, usage, clarify, suggestions);
   - `event: error`: a plain message.
2. Run the agent in a worker thread and pass events through a queue, so the event loop isn't blocked. Send a comment line (`: ping`) every 10 seconds while waiting on the rate pacer, so proxies and the Cloudflare tunnel don't drop the connection.
3. **The client can stop it:** when the page disconnects (Stop button), the worker stops at the next step or token and the LLM stream is closed.
4. `/ask` stays exactly as it is (`check_answers.py` and the ablations use it).
5. Rate limits and the 500-character question limit apply to `/ask/stream` too.
6. **Suggested follow-ups,** in code with no LLM call: `done` carries 2–3 suggestions built from the task type, topic, slots and the sources used (after a fee answer: "When is the fee due?", "What is the hostel fee for [programme]?", "How do I apply for fee remission?"), checked against a small set of templates known to be answerable (the HOW-TO-RUN demo questions and the 105 cases' topics).

**Tests:** with a fake streaming LLM, `/ask/stream` emits step → token… → done in order, and the `done` JSON equals what `/ask` gives for the same fake run; a disconnect stops the worker; the ping comment appears during a long wait; suggestions for a fee answer are fee-related.

**Done when:** tests pass; a manual run on port 8020 (fake LLM via an env switch for tests, or the dev model) shows events arriving with `curl -N`. Commit.

---

## Step 7. The chat page, like Claude or ChatGPT

Rework `frontend/index.html` in the worktree. Keep its escaping rules (`escapeHtml`, safe links only) and every existing feature (sources, "How I found this", badges, clarify buttons, profile, 👍/👎). Add:

1. **Streaming:** read `/ask/stream` with `fetch` + `ReadableStream`. Show the steps live as small grey lines with a spinner ("Searching VNIT documents…", "Opening: Fee notice S-27…"), then the answer growing word by word. When `done` arrives, fold the steps into the collapsible "How I found this", and render sources, badge and suggestions. On `replace`, swap in the revised answer with a small note "Corrected after checking against the documents."
2. **Controls under each answer:** Copy, Regenerate (asks the same question again), 👍/👎. On the latest question: **Edit** (puts it back in the box). While streaming: a **Stop** button (AbortController).
3. **Suggested follow-ups** as chips under the last answer. Clicking one asks it.
4. **New chat** button (clears turns and profile), and an empty-state screen with 4 example questions and one line on what it can do ("Answers come only from VNIT's own documents, with sources, and every figure is checked.").
5. **Markdown:** headings, bold, lists, numbered steps, links, and **tables** (for compare answers), all escaped.
6. **Layout like the familiar chat apps:** a centred column about 760 px wide, the input fixed at the bottom with a growing textarea (Enter sends, Shift+Enter adds a line), the user's messages right-aligned in bubbles, the assistant's left-aligned without bubbles, and dark mode following the system (the page already has it). Works at 360 px.
7. Keep conversation state in memory only (turns, profile), as before, for privacy. Optional: a "Keep this chat if I reload" checkbox that uses `sessionStorage`, off by default, wrapped in try/catch.
8. The old `/ask` path stays as the fallback if `/ask/stream` fails (an older server).

**Check by looking:** screenshots with headless Edge (the `tools/shot.sh` approach from `vnit-website`; copy the idea, don't edit that repo here) of the empty state, a streamed answer, a compare table and a draft, desktop and phone. Open each PNG and fix what looks wrong. Use the fake-LLM server mode on 8020 for screenshots so no quota is spent.

**Done when:** every feature above works in the screenshots, nothing from the old page is lost (write a checklist in REPORT11), escaping is intact (a test question containing `<img src=x onerror=alert(1)>` shows as text). Commit.

---

## Step 8. The website widget gets the same

In `vnit-website/`, on a new branch `agent-v2` (`git -C vnit-website switch -c agent-v2`; `master` untouched):
1. Port Step 7's streaming, live steps, Stop, Copy, Regenerate, suggestions and table rendering into `assets/js/vnit-assistant.js` and its CSS. Keep the floating-panel design and the page-based suggested questions.
2. The widget prefers `/ask/stream` and falls back to `/ask`.
3. Rebuild with `build_site.py` and run its checks (`check_links`, `check_pages`, `check_faithful`): still 0 problems.
4. v2 serves the site the same way v1 does. Check that `api/main.py`'s `SITE` path still resolves from the worktree (`vnit-chatbot-v2/api/` → `../../vnit-website/dist`). The path is relative to the file, so it should.

**Done when:** the widget works against v2 on 8020 (screenshot), the site checks pass, and `vnit-website` `master` is unchanged. Commit on `agent-v2` there.

---

## Step 9. Tests and measurements

1. **No-key:** `test_agentic.py` (all v1 and v2 tests), `chunk_ranks`, `fact_ranks`, `evaluate`, `evidence_check`: retrieval numbers equal the baseline. With `AGENT_V2=off`: every v1 test passes unchanged.
2. **New agentic cases** in `check_answers.py`, as a set `--set agentic` (about 15), each with expected patterns from VNIT's documents in the existing style:
   - 3 multi-part (two programmes' fees plus a due date);
   - 2 compare;
   - 2 summarise;
   - 2 explain;
   - 2 draft (the office email must appear, and the draft label);
   - 2 multi-turn with pronouns ("how do I pay it?");
   - 1 Hindi and 1 Hinglish;
   - plus 2 `general` questions that must be labelled, and 2 must-decline questions phrased to tempt the `general` path ("what was the JoSAA closing rank for CSE at VNIT?").
   They go to their own results file (`--config agent_v2_dev`), never to `answer_check.json`.
3. **Live, dev model only** (if Step 0 found one): run `--set agentic --config agent_v2_dev --pause 30` with `GENAI_MODEL=<DEV_MODEL>`, and the same for 15 of the original cases (a spread: fees, hostel, calendar, placements, people, 2 must-decline, 2 clarify) to check v2 hasn't made the basics worse. Record per question: pass, steps, tool calls, tokens, seconds. Note in the report that the dev model isn't the final model, so these show the agent works, not the final score.
4. **Cost and speed table:** v1 versus v2 on the dev-model runs, with average tokens, seconds and tool calls per question. If v2 averages more than 2× v1's tokens on the original cases, lower `AGENT_V2_MAX_STEPS` or `AGENT_V2_BUDGET` and record it.
5. If there's no dev model, write the exact commands for Step 3's runs, to be done after the ablations finish.

**Done when:** all no-key checks pass; the agentic and regression runs are recorded (or their commands written); the cost table is in REPORT11; EXPERIMENTS-LOG gets a new §37 "Agent v2" in the worktree.

---

## Step 10. Docs, the merge plan and the morning report

1. In the worktree: README (a "v2" section), APPLICATION.md (the loop, tools, task types, streaming), HOW-TO-RUN.md (how to start v2). Add `start_chatbot_v2.bat`: same as `start_chatbot.bat`, but in the `vnit-chatbot-v2` folder, on **port 8001**, opening `http://127.0.0.1:8001/`. Also make it open `/site/` with a second shortcut, `start_website_v2.bat`.
2. **The merge plan** (in REPORT11, for after the ablations finish):
   1. run the full 105 cases on v2 with the real model: `--config agent_v2` (about 2 days of allowance);
   2. add "agent v2" as a row in the ablation table (`ablation_table.py` already reads per-config files);
   3. merge only if v2 is **not lower** than v1 on the 105 and all must-decline cases are still refused. Write the exact commands: `git -C vnit-chatbot merge agent-v2`, then `git -C vnit-website merge agent-v2` and rebuild the site.
   4. Until then, the demo can show both: v1 on 8000 (measured) and v2 on 8001 (the Claude-like one).
3. **REPORT11.md, "Good morning" at the top**, in plain words:
   - what v2 can do now that v1 couldn't, as a list Shivanand can read out in a demo;
   - which steps are DONE, PARTIAL or FAILED;
   - the live results on the dev model (or "no dev model, so these are fake-LLM tests only"), and the cost table;
   - the 6-click demo: start `start_chatbot_v2.bat` → ask a multi-part fee question and watch the steps stream → click Stop on a second one → ask "compare B.Tech and B.Arch fees" (table) → "write an email to the hostel office asking for a fee extension" → ask the same in Hindi;
   - confirmation that `vnit-chatbot/` is untouched (`git status` identical to Step 0) and that the ablations are still running (log tail);
   - the merge plan, in short;
   - one honest line for the slides: "Same open model (gpt-oss-120b); what changed is the agent around it: memory, planning, more tools, streaming and the interface."

**Done when:** docs and the launchers exist, PROGRESS-11 has every step marked, and the last commit is on `agent-v2`.

---

## Don't do

- Don't edit, build, commit, check out or reset anything in `vnit-chatbot/`. Don't touch the ablation runner, its window, log or results.
- Don't call `openai/gpt-oss-120b` or `openai/gpt-oss-20b` tonight. Live tests use only the dev model.
- Don't merge or push. Don't touch `main` or `vnit-website`'s `master`.
- Don't let a ChatGPT-like feature invent VNIT facts: general answers carry no VNIT figures, drafts' facts are verified, must-decline cases still decline.
- Don't add LLM calls for critique or judging. Reflection is code.
- Don't add dependencies, frameworks or CDNs.
- Don't store conversations, profiles or IP addresses on the server.
- Don't print, read or commit keys. Don't delete files.
