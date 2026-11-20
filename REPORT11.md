# Runbook 11 report: agent v2

## Good morning

**In short: version 2 is built, tested and committed on its own branch, and runs next to version 1.** It streams its answers, shows its steps live, remembers the conversation, plans, uses more tools, does more kinds of task, answers in Hindi and Marathi, and has the usual chat buttons. Version 1 and the ablations were not touched. Nothing is merged or pushed.

**What v2 can do that v1 couldn't** (a list to read out in a demo):
1. It **writes the answer word by word**, and shows what it is doing while it works: "Searching VNIT's documents…", "Plan: 1. … 2. …", "Opening: Fee notice S-27…". You can press **Stop**.
2. It **remembers the conversation**: the last 6 questions and answers, so "how do I pay it?" and "which of those is cheaper?" work.
3. It **plans and keeps going**: a multi-part question gets a short plan, up to 6 rounds of lookups (3 at a time), and it stops when every part is found.
4. **More tools**: the newest notices, a **live** vnit.ac.in page, today's date, and the right office to contact.
5. **More kinds of task**: **compare** (a table), **summarise** a notice, **explain** a procedure step by step, **draft** an email to an office (with its verified address), and short **general** answers ("what is CGPA?"), always labelled as not from VNIT's documents.
6. **Hindi, Marathi and Hinglish**, with the figures exactly as in the documents.
7. **A chat page like ChatGPT's**: Copy, Regenerate, Edit, suggested next questions, New chat, tables, dark mode, phones. The website's floating assistant got the same.
8. Still the same promise: **VNIT facts only from VNIT's documents, with sources, every figure checked.** The must-decline questions (Wi-Fi password, JoSAA ranks, GATE cut-offs, a warden's address, old fees) are still declined; they can never be taken for "general" questions (tested).

**Steps:** 0-10 all **DONE**. Two things are only partly measured, because of the free allowance (below).

**Live results on the dev model** (`qwen/qwen3.8-27b`; the ablations had the gpt-oss allowance, so v2 was **not** tried on the final model tonight):
- 13 trial questions through the agent: **11 right, 1 half right, 1 poor.** Multi-part fees and hostel: right. Placements 2025-26: it called the season "ongoing" instead of giving 678 (half right). "Is the Summer 2027 deadline over?": it found no date and still said "not over" (poor). Compare, summarise, explain, draft, lookup: right. Hindi, Marathi (it opened the live Director page by itself) and Hinglish: right.
- The agentic test set (19 cases): **2 of 2 asked so far passed**, then the dev model's daily allowance ran out. A loop keeps resuming it until 07:30 (see "Final numbers" at the end of this section).
- **Cost:** on the trials, v2 used about **12,000 tokens and 2 minutes** a question, against v1's 4,500 tokens and 24 s. That is ~2.6× on hard questions; a simple question costs the same in both. The like-for-like comparison (15 regression questions through both on the same model) is queued; if v2 is above 2× there, set `AGENT_V2_BUDGET=10000`.

**Automated checks (no key):** 112/112 tests (v1's 73 + 39 new), and v1's 73 pass unchanged with `AGENT_V2=off`. Search measurements are unchanged: 78/82, 13/18, 16/19, 80/82 + 11/11.

**The 6-click demo:**
1. Double-click `vnit-chatbot-v2\start_chatbot_v2.bat` (opens `http://127.0.0.1:8001/`).
2. Ask *"What is the yearly tuition fee for B.Tech and for B.Arch in the OPEN category, and what is the hostel fee for first year B.Tech girls for Winter 2026?"* and watch the plan and lookups stream, then the answer.
3. Ask anything else, and click **■ Stop** while the steps are showing.
4. Ask *"Compare the yearly tuition fees for B.Tech and B.Arch"*: a table.
5. Ask *"Write an email to the hostel office asking for a fee extension"*: a draft with AR_HOSTEL@vnit.ac.in, marked "Draft — check before sending."
6. Ask *"बी.टेक लड़कियों की पहले वर्ष की हॉस्टल फीस कितनी है? विंटर 2026"*: the same fee, answered in Hindi.

**Before a demo, while the ablations still run:** v2 uses the same models as v1, so a demo spends the ablations' allowance. To demo v2 without it, open `start_chatbot_v2.bat` in Notepad and remove `REM ` from the `AGENT_MODEL=qwen/qwen3.8-27b` line. To rehearse without any AI at all, see `HOW-TO-RUN.md` §2a (`AGENT_FAKE_LLM=on`).

**Untouched, as required:**
- `vnit-chatbot/`: `git status` identical to the start (on `main` at `ddcb7cd`; only the ablations' result files are new there).
- The ablations are still running. Log tail at 02:50: `one-shot: Answer check (oneshot): 77/88 passed (17 not asked yet)`.
- `vnit-website`'s `master` is still at `fc7c5f8`; the new widget is on its branch `agent-v2`. That folder is now checked out on `agent-v2`, so v1 on port 8000 also shows the new widget (it falls back to `/ask` and works). `git -C vnit-website switch master` and `python build_site.py` give the old one back.

**The merge plan (after the ablations finish):**
1. Run all 105 cases on v2 with the real model (about 2 days of allowance):
   ```
   cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-chatbot-v2/pipeline
   export GENAI_API_KEY=$(head -1 ~/groq-key.txt | tr -d '\r\n ')
   python check_answers.py --config agent_v2 --pause 30 --resume     # run again each day until it says 105/105 asked
   ```
2. Add "agent v2" as a row of the ablation table. v2's `ablation_table.py` already lists it (`answer_check_agent_v2.json`); copy the ablations' result files next to it and print the table:
   ```
   cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-chatbot-v2
   cp ../vnit-chatbot/data/processed/answer_check_{oneshot,no_tools,agent_30oct,crag,clarify,full_hard}.json data/processed/
   cd pipeline && python ablation_table.py
   ```
3. Merge **only if** v2 is not lower than v1 on the 105 (v1: 105/105 saved) **and** every must-decline case is still refused:
   ```
   git -C vnit-chatbot merge agent-v2
   git -C vnit-website switch master && git -C vnit-website merge agent-v2
   cd vnit-website && python build_site.py && python tools/check_links.py && python tools/check_pages.py && python tools/check_faithful.py
   ```
4. Until then, the demo can show both: **v1 on 8000** (measured) and **v2 on 8001** (the Claude-like one).

**One honest line for the slides:** "Same open model (gpt-oss-120b); what changed is the agent around it: memory, planning, more tools, streaming and the interface."

**Final numbers:** written at the end of this run, under Step 10 below.

## Step 0. Worktree, branch, frozen index, dev model, baseline

- **The ablations are running and were not touched.** Log tail at the start (00:50, 21 Nov): `one-shot: Answer check (oneshot): 74/85 passed (20 not asked yet)`, stopped for the day's allowance as expected; the runner retries every half hour. No Python process of theirs was running at that moment (they were waiting).
- **Worktree:** `git -C vnit-chatbot worktree add ../vnit-chatbot-v2 -b agent-v2 final-index-2026-11-20`, then `merge --ff-only ddcb7cd` fast-forwarded (docs only). `vnit-chatbot/`'s `git status --short` before and after: identical (only the ablations' three untracked result files and `.claude/`), still on `main` at `ddcb7cd`.
- **Frozen index** copied from `~/vnit-chatbot-backups/final-index-2026-11-20/`: `index.pkl` 32,383,236 bytes, `chunks.jsonl` 8,626,639, `facts.db` 10,977,280, the same sizes as v1's (and `index.pkl`'s MD5 is identical). Not in git.
- `data/feedback/` created empty; no students' data copied.
- **Dev model:** `GET /models` lists `allam-2-7b`, `canopylabs/orpheus-*` (speech), `meta-llama/llama-prompt-guard-2-*`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b`, `whisper-*`. None of the preferred ones (kimi-k2, qwen3-32b, llama-3.3-70b, llama-4) exists for this key, so **`DEV_MODEL = qwen/qwen3.8-27b`**: a general model with its own allowance. A tiny tool-calling test returned a correct `tool_calls` reply (305 tokens; limits 8,000 tokens a minute).
- **Baseline in the worktree, no key** (logs in `../_trash/r11/`):

| Check | REPORT10 | Worktree |
|---|---|---|
| `test_agentic.py` | 73/73 | **73/73** |
| `chunk_ranks.py` (top 7) | 78/82 | **78/82** |
| `fact_ranks.py` | 13/18 | **13/18** |
| `evaluate.py` | 16/19 | **16/19** |
| `evidence_check.py` | 80/82 + 11/11 | **80/82 + 11/11** |

**Done when:** worktree on `agent-v2` with the frozen index, `vnit-chatbot/` unchanged, dev model recorded, baseline equals REPORT10. **Met.**

## Step 1. Conversation memory

- `pipeline/memory.py` (new): keeps the last **6** turns `{q, a}`, each answer cut to **600** characters without its `[1]` numbers, "Who can help" footer or "could not confirm" note, and the whole block within **~1,500 tokens** (oldest dropped first). Nothing is stored.
- `/ask` (and `/ask/stream`) accept `turns: [{"q", "a"}]` besides the old `history`, which still works (v1, `check_answers.py`).
- `followup.resolve(..., turns=...)`: the code fast path is unchanged; the LLM rewrite is shown the questions **and answers**, so "how do I pay it?" after a B.Tech fee answer is rewritten with the programme. Item references ("the second one", "which one is cheaper", "the latter") count as follow-ups only when answers are remembered (v2), so v1's behaviour is unchanged.
- The agent's first message carries a "Conversation so far" block, labelled as context: "any VNIT figure, date or contact you repeat from it must be found again in a passage and cited". It is never given to the verifier.
- **Tests (fake LLM):** 6 turns kept / 7 trimmed to 6; the token cap drops the oldest; answers trimmed and footers dropped; "how do I pay it?" rewritten with "B.Tech" (and the no-key fallback keeps it too); item references are follow-ups only with answers; a figure found only in an earlier answer is **unsupported**; `AGENT_V2=off` ignores the answers and its prompt equals v1's exactly.
- **Done when:** tests pass; no-key checks equal the baseline (table at the end of Step 6). **Met.**

## Step 2. The agent loop v2

- `pipeline/agent_loop.py` (new) imports planner.py's client and pacer, `Evidence`, `_final_prompt`, citations and the verifier step; it does not copy them. Only the loop differs:
  - **plan:** the first reply may list 1-4 parts, shown as a `plan` step. A part is marked done by the model ("Done: 1, 3") or by code: a new passage covers most of the part's rarer words and holds the kind of fact it asks for (an amount, a date, a count, a contact).
  - **act:** up to `AGENT_V2_MAX_STEPS` (6) rounds, up to 3 calls per round run **in parallel** (a thread pool; `Evidence.add` got a lock).
  - **stop:** the model answers; every plan part is done; the next round would pass `AGENT_V2_BUDGET` (14,000); or two rounds in a row found nothing new.
  - **reflection, in code:** after each round, one line such as "That round found 2 new passage(s) but none gives a date. Try the document that should state it…", plus "Steps left: 4; about 8,200 tokens left".
  - **context control:** past `PROMPT_BUDGET`, the conversation is rebuilt as one message with the cited passages, then the newest, then the first search, and the titles set aside (to reopen with `read_document`).
  - a repeated identical tool call is not run again (seen live: the dev model asked `read_document` the same thing twice).
  - answer, verify, revise once, hand-off: as in v1. Fallbacks (one-shot, then extractive) unchanged.
- `planner._LLM.chat` got two optional arguments (`schemas`, `extra`); left out, the request is exactly v1's.
- **Tests (fake LLM):** a 4-round run with 3 calls at once (measured: 3 running together); stop on budget; stop when stuck, with the reflection line; plan parts tracked and the stop when all are done; the model marking parts itself; verify and revise; compaction; a repeated call skipped; `AGENT_V2=off` calls `planner.run`, on calls `agent_loop.run`.
- **Live, dev model** (`qwen/qwen3.8-27b`), three multi-part questions:

| Question | Result | Tokens | Rounds | Tool calls | Seconds |
|---|---|---|---|---|---|
| B.Tech and B.Arch OPEN tuition, and first-year B.Tech girls' hostel fee | **right** (₹1,25,000 both; ₹32,650); a plan of 3 parts, all found, then it stopped | 10,921 | 1 | 2 (parallel) | 157 |
| Students placed in 2025-26, and highest B.Tech package 2024-25 | **half right**: ₹64 LPA right; said the 2025-26 count is "not yet available" (the T&P page says 678) | 15,144 | 2 | 2 | 104 |
| M.Tech mess deposit, and when first-years join the mess | **right** (₹48,000; from the day of physical reporting) | 14,423 | 2 | 3 | 103 |

  Most of the seconds are the rate pacer waiting for the 8,000-tokens-a-minute allowance: each round is ~5,000 tokens with v2's longer tool list.
- **Done when:** tests pass; retrieval unchanged; 3 live multi-part traces recorded. **Met** (one of the three half wrong, recorded).

## Step 3. New tools

- In `tools.py`, offered only to v2 (`active_schemas(v2=True)`; v1's list is unchanged). Each result is registered through `Evidence` as a `[P#]` passage:
  - `latest_notices(category, n)`: converted, kept documents (status "ok" and text in `data/raw`) from `inventory.json` + `status.json`, newest first, by category (fees, academics, hostel, scholarship, placement, admission, recruitment);
  - `fetch_vnit_page(url)`: **only** `vnit.ac.in` and its sub-sites (the host is compared whole, so `vnit.ac.in.evil.com` is refused); robots.txt, the crawler's user agent, 1 request a second, 10 s timeout, 2,500 characters, a 24-hour cache in `data/cache/pages/` (git-ignored), and the crawled copy when the site can't be reached. `LIVE_PAGES=off` removes it;
  - `today()`: today's date in IST, as a passage, so the verifier can check a date taken from it;
  - `contact_office(topic)`: the office from `data/contacts.json` for a topic.
- One line per tool in the prompt; every description is under 25 words.
- **Tests (no internet):** order and category of `latest_notices` on the real inventory; five bad URLs refused (another host, look-alike hosts, `ftp:`, `javascript:`); the saved page `pipeline/fixtures/vnit_section_hostel.html` parsed, and the second open served from the cache; the crawled-copy fallback; `today()` verified as a passage; `contact_office("hostel room refund")` gives the Hostel Section; v2's tools never offered to v1.
- **Live, dev model:**
  - "any new fee notice?" called **`latest_notices`** and answered with the S-27 fee notice of 6 Nov 2026 and its 1 Nov – 23 Dec window, plus the two Summer 2027 notices of the same day (9,395 tokens, 145 s).
  - "is the Summer 2027 fee payment deadline over?" did **not** call `today` (today's date is already in its prompt) and found no date in the Summer 2027 instructions. It said so, but opened with "not over", which doesn't follow. It also repeated a lookup, which led to the repeated-call check above (13,329 tokens, 92 s).
  - Unasked, the Marathi Director question in Step 5 opened the **live** Director page with `fetch_vnit_page`.
- **Done when:** tests pass; no-key checks equal the baseline; the two live questions run. **Met**, with the `today` gap recorded.

## Step 4. More kinds of task

- `router.task()`: `lookup`, `compare`, `summarise`, `explain`, `draft`, `general` or `chat`, by code rules in that order. A "Task: compare." trace line, and one instruction line per task for the agent (`router.TASK_LINES`).
- **general:** only a short concept question ("what is CGPA?") with nothing VNIT-specific or time-sensitive in it (no fees, ranks, cut-offs, dates, salaries, passwords, people or years). One LLM call, no search. The label "*General answer, not from VNIT's documents.*" is added by code, and the verifier runs with no passages, so any figure is flagged in a note. With no key, it is looked up instead.
- **draft:** the label "Draft — check before sending." is added by code if the model leaves it out; the office's email comes from `contact_office` and is verified like any figure.
- **chat:** "what can you do?" lists the new abilities (v2 only; v1's text is unchanged).
- **Tests:** 25 phrasings mapped to task types; the 10 must-decline cases, and 4 more phrased to tempt `general`, are never `general` and always route to a lookup; a fake-LLM draft carries `AR_HOSTEL@vnit.ac.in` from `contact_office`, verified, with the administrative-officers page as its source; a fake-LLM compare answer keeps its markdown table with numbered citations; a general answer is labelled and has no sources, and a VNIT figure in one is flagged.
- **Live, dev model, one of each** (trimmed):
  - **compare** "B.Tech vs B.Arch OPEN tuition": a table, B.Tech ₹1,25,000 [1], B.Arch ₹1,25,000 [2], verified (6,312 tokens). A note saying a sheet "does not restate the category" set off the "Who can help" line needlessly.
  - **summarise** "the S-27 fee notice": 5 bullets (dated 6 Nov 2026; 1 Nov – 23 Dec 2026 window; registration only after fee validation; the AIMS path; DASA fees in USD), verified after one revision. 20,606 tokens, over the 14,000 budget: the budget stops tool rounds, but the final answer and the revision come after it.
  - **explain** "how do I apply for fee remission?": 3 numbered steps (the documents, including the income certificate and the ₹100 affidavit; the Google form; handing in the originals to the Deputy Registrar, Academic) and the extended date 14/10/2026. 4 tool calls, 3 of them in one round; 13,622 tokens.
  - **draft** "email to the hostel office … extension": "Draft — check before sending.", To: Assistant Registrar (Hostel Section), `AR_HOSTEL@vnit.ac.in` [1], the 15 August 2026 deadline and the ₹5,000-a-month fine from the outstanding-fees notice [2], placeholders [Your Name], [Roll Number]; verified.
  - **general** "what is CGPA?": labelled, 203 tokens, 0.3 s, no figures.
  - **chat** "what can you do?": the new list, no LLM call.
  - **lookup** "Who is the Registrar?": CMA Shri S. S. Jagdale; 4,169 tokens, 7 s.
- **Done when:** tests pass; no-key checks equal the baseline; one live answer of each type recorded. **Met.**

## Step 5. Hindi, Marathi and Hinglish

- `pipeline/language.py` (new): Devanagari is Hindi or Marathi, told apart by very common words of each (है/क्या/कितनी vs आहे/काय/किती); Latin-script Hindi by words like kitni, kya, hai, kab, kaise, hoga.
- The first search runs on English keywords made in code. Hinglish keeps its English words; Hindi and Marathi keep anything in Latin letters or digits and translate a small glossary (फीस/शुल्क → fee, छात्रावास/वसतिगृह → hostel, लड़कियों/मुलींच्या → girls, बी.टेक → B.Tech, …). The trace says so, and `understood_as` shows the English search.
- The agent is told the language: search in English; answer in the student's language, with numbers, amounts, dates, emails and titles exactly as in the passages, in digits 0-9. Devanagari digits in an answer are turned into 0-9 in code before verifying.
- Greetings and thanks in Hindi, Marathi and Hinglish get fixed replies in that language (no LLM); a general answer is written in the language too.
- **Tests:** 12 phrasings (3 each of Hindi, Marathi, Hinglish and English) detected right; the Hinglish hostel question's first search is "hostel fees", a Hindi one's "B.Tech girls how much hostel fee"; a Hindi answer with "Rs. 32,650" and one with "३२६५०" both verify; नमस्ते and धन्यवाद are answered directly.
- **Live, dev model:**
  - Hindi "बी.टेक लड़कियों की पहले वर्ष की हॉस्टल फीस कितनी है? विंटर 2026": "B.Tech. girls के लिए 2026-27 में पहली साल का Hostel Fee **Rs. 32650/-** (Winter 2026 session) है।", plus the Summer 2027 fee and the mess deposit. **Right**, verified (15,419 tokens).
  - Marathi "VNIT चे संचालक कोण आहेत?": "VNIT Nagpur चे सध्याचे (2026) **Director Prof. (Dr.) Prem Lal Patel** आहेत.", after opening the live Director page. **Right** (8,524 tokens).
  - Hinglish "btech ki yearly tuition fee kitni hai open category ke liye?": "B.Tech ka **yearly tuition fee OPEN/OBC/EWS category ke liye Rs. 1,25,000** hai", through `lookup_table`. **Right** (11,131 tokens). The first try hit the per-minute limit and fell back; it was asked again a few minutes later.
- **Done when:** tests pass; one Hindi, one Marathi and one Hinglish question answered right. **Met.**

## Step 6. Streaming API

- `POST /ask/stream` (same body, same 500-character limit and rate limits) returns Server-Sent Events: `step` (each trace line as it happens), `token` (pieces of the answer as Groq streams it, with `[P3]` turned into `[1]` on the fly), `replace` (the revised answer after the verifier), `done` (exactly what `/ask` returns) and `error` (a plain message).
- The answer runs in a worker thread and passes events through a queue. A `: ping` comment goes out after 10 s of silence (the rate pacer can wait that long).
- **Stop:** when the page disconnects, the stream sets a cancel flag; the agent stops at its next step or token and closes the stream from Groq.
- `/ask` is unchanged. Streaming falls back to an ordinary call if the stream fails, so it changes how an answer arrives, never whether it does.
- **Suggested follow-ups,** in code: 2-3 per topic, all taken from cases the saved results show are answered right, with `{programme}` filled from the question. A repeat of the question is skipped; a draft or a procedure also gets "Which office should I contact about this, and how?".
- **Tests:** with a fake streaming LLM, step… → token… → done in order; the streamed text is the final answer with numbered citations, and **the `done` JSON equals what `/ask` returns for the same fake run**; the limits apply to `/ask/stream`; a disconnect sets the cancel flag and a cancelled run stops; Stop after the first word closes the LLM stream (only "one " arrives); the ping comment appears while waiting; a hostel fee answer gets fee-related suggestions.
- **Manual run** on port 8020 in fake-LLM mode (`AGENT_FAKE_LLM=on`; `pipeline/fake_llm.py` is a pretend model that answers from the passages, for screenshots without quota), with `curl -N`: `route`, `route` at 0.0 s; `: ping` at 10.2 s while the first search ran; `grade`, `search`, `plan` at 10.2-10.4 s; `tool`, `reflect` at 20.3 s; then 80 `token` events, `answer`, `verify` and `done`.
- **Done when:** tests pass; events seen arriving with `curl -N`. **Met.**

### No-key checks after Steps 1-6

| Check | Baseline | After Steps 1-6 |
|---|---|---|
| `test_agentic.py --v1-only` with `AGENT_V2=off` (v1's tests, v1's behaviour) | 73/73 | **73/73** |
| `evidence_check.py` (v2 on) | 80/82 + 11/11 | **80/82 + 11/11** |
| `chunk_ranks.py` | 78/82 | **78/82** |
| `test_agentic.py` (v1 + v2 tests together) | 73/73 | final count in Step 9 |

`fact_ranks.py` and `evaluate.py` call only the search (`query.py`), which v2 doesn't change; they are re-run in Step 9.

## Step 7. The chat page, like Claude or ChatGPT

`frontend/index.html` rewritten (plain JS, no framework, no CDN):

- **Streaming:** reads `/ask/stream` with `fetch` and a stream reader. The steps appear as small grey lines with a spinner on the newest ("Searching VNIT's documents…", "Opening: Fee notice S-27…"), then the answer grows word by word behind a blinking cursor. On `done`, the steps fold into "How I found this", and the sources, badge and suggestions appear. On `replace`, the revised answer is swapped in with "Corrected after checking against the documents."
- **Controls:** under each answer Copy, Regenerate (the latest answer is replaced in place; an older one is asked again at the bottom) and 👍/👎; **Edit** on the newest question (puts it back in the box and removes that exchange); while an answer is being written, the send button becomes **Stop** (`AbortController`), and the server stops the work.
- **Suggested follow-ups** as chips under the newest answer.
- **New chat** (forgets the turns and the profile) and an empty screen with 4 example questions and the line "Answers come only from VNIT's own documents, with sources, and every figure is checked."
- **Markdown:** headings, bold, italics, lists, numbered steps, http(s) links and **tables**, all escaped first.
- **Layout:** a centred 760 px column, the box fixed at the bottom and growing (Enter sends, Shift+Enter adds a line), the student's messages right-aligned in bubbles, the assistant's left-aligned without a bubble, dark mode from the system. Works at 360 px (the developer-only "server" box is hidden on phones).
- The turns and profile live in memory only. "Keep this chat if I reload" (off by default) uses `sessionStorage`, wrapped in try/catch.
- If `/ask/stream` is missing (an older server) or fails before answering, the page uses `/ask`.
- `/?q=<question>` asks a question when the page opens (used for the screenshots; the website could link to answers this way).

**Screenshots** (`checks/`, fake-LLM server on 8020, so no quota; the answers' wording is the pretend model's, labelled "agent v2 (fake-llm)"). Each was opened and looked at:

| Screenshot | What it shows |
|---|---|
| `empty_desktop.png` (dark), `empty_phone.png` (360 px) | the empty screen with 4 example cards (left-aligned after a fix), the one-line promise, New chat, the round send button |
| `answer_live.png` (light) before the answer finished | live steps with ✓ and the spinner, the blinking cursor, the Stop button |
| `answer_desktop.png` (light), `answer_phone.png` | a finished answer: numbered sources, "How I found this (9 steps, 1 lookup)", Copy, Regenerate, 👍/👎, the mode, "✓ 8 figures checked", three fee/mess suggestion chips, Edit under the question |
| `compare_desktop.png` (light), `compare_phone.png` (dark, 360 px) | a compare answer as a bordered table with header row and citation numbers; on the phone the table fits without sideways scrolling |
| `draft_desktop.png` (dark) | a draft starting "Draft — check before sending.", placeholders [Your name] [Roll number], and "Which office should I contact about this, and how?" first among the suggestions |
| `stop_desktop.png` | Stop pressed during the steps: "*Stopped.*", no rating buttons (removed for stopped answers after looking) |
| `escape_desktop.png` | the question `<img src=x onerror=alert(1)> hostel fee?` shown as plain text in the bubble; no image, no script |

**Nothing from the old page is lost:**

| Old feature | v2 page |
|---|---|
| `escapeHtml` before any Markdown; source links only for http(s) | kept (links in answers only for http(s) too) |
| sources as numbered chips | kept |
| "How I found this" with step kinds | kept, with the new kinds (planned, noticed, tidied, stopped) |
| verification badge (✓ figures checked / ⚠ not confirmed) | kept |
| "Understood as" line | kept |
| clarify buttons that remember the choice in the profile | kept |
| "Clear my details" | kept |
| 👍/👎 to `/feedback` | kept |
| starter questions | now the 4 example cards |
| server address box | kept (hidden on phones) |
| Enter sends, Shift+Enter new line, growing box | kept |
| dark mode | kept |
| no storage | kept (the reload option is off by default and per-tab) |

**Done when:** every feature works in the screenshots, nothing lost (checklist above), escaping intact. **Met.**

## Step 8. The website widget gets the same

- `vnit-website` on a new branch **`agent-v2`** (`master` still at `fc7c5f8`, unchanged). In `assets/js/vnit-assistant.js` and its CSS:
  - prefers `/ask/stream` and falls back to `/ask` (so it still works with v1's server);
  - live steps with a spinner, the answer written as it streams, Stop (the Ask button becomes Stop), Copy, Regenerate, suggested follow-ups as chips under the newest answer, tables and http(s) links in answers, "Corrected after checking…" on `replace`;
  - the turns `{q, a}` sent as `turns`, in memory only; the floating-panel design and the page-based suggested questions kept.
- Rebuilt with `build_site.py`: 1,562 pages. Checks: `check_links` **0 broken internal links**; `check_pages` **1,562 pages, 0 problems**; `check_faithful` **200,125 pieces of text, 0 not found in the crawl**.
- v2 serves the site the same way: `api/main.py`'s `SITE` is relative to the file, so from `vnit-chatbot-v2/api/` it is `VNIT-Website-Chatbot/vnit-website/dist`; `/site/` worked on 8020.
- **Screenshots** on 8020: `widget_live.png` (the widget's live steps and its Stop button) and `widget_desktop.png` (a compare table inside the floating panel, with Copy, Regenerate, ratings and three suggestion chips).
- Committed on `vnit-website`'s `agent-v2`: `0ced9ea`.
- **Done when:** the widget works against v2 on 8020, the site checks pass, `master` unchanged. **Met.**

## Step 9. Tests and measurements

**No key** (all on the frozen index):

| Check | Baseline (Step 0) | v2 |
|---|---|---|
| `test_agentic.py` (v1 + v2 tests) | 73/73 | **112/112** (73 + 39) |
| `test_agentic.py --v1-only` with `AGENT_V2=off` | 73/73 | **73/73**, unchanged |
| `chunk_ranks.py` | 78/82 | **78/82** |
| `fact_ranks.py` | 13/18 | **13/18** |
| `evaluate.py` | 16/19 | **16/19** |
| `evidence_check.py` | 80/82 + 11/11 | **80/82 + 11/11** |

Retrieval is unchanged, as intended: v2 changes what happens after the first search, not the search.

**New cases** in `check_answers.py`:
- `--set agentic` (`AGENTIC`, 19 cases): 3 multi-part, 2 compare, 2 summarise, 2 explain, 2 draft (the office's email and the draft label must appear), 2 multi-turn ("how do I pay it?", "which of the two is cheaper?"; the earlier turns are asked too and their answers remembered), 1 Hindi, 1 Hinglish, 2 general (must carry the label), and 2 must-decline phrased to tempt the general path (must decline and must *not* carry the general label). Expected figures come from the same documents the existing cases use.
- `--set regression` (`REGRESSION_V2`, 15 of the original cases: B.Tech and M.Sc fees, the girls' and boys' hostel fees, a mid-sem date, Holi, placements, the 2024-25 company count, Director, Dean (Academic)'s email, Registrar, 2 must-decline, 2 clarify).
- Both save only to `answer_check_<config>.json` and need `--config`; `answer_check.json` is never touched. `reached_llm` now also counts a "general (model)" answer.
- `pipeline/v2_table.py` prints the pass counts and the cost table from the saved runs.

**Live, dev model only.** Started 01:59 with `--set agentic --config agent_v2_dev --pause 30`, `AGENT_MODEL` and `GENAI_MODEL` = `qwen/qwen3.8-27b`:
- `multi_tuition_and_s27_deadline` **PASS** (₹1,25,000; 23 Dec) and `multi_hostel_girls_and_mtech_mess` **PASS** (₹32,650; ₹48,000); 16,008 tokens, 160 s and 3 tool calls a question on average.
- Then the dev model's rolling daily allowance ran out (about 160,000 tokens had gone on the Step 2-5 trials). A background loop resumes the agentic set every 20 minutes until it is complete, then the regression set through v2, then the same 15 through v1 (`AGENT_V2=off`) for a like-for-like cost table, and stops at 07:30. Its results are added below if they arrive before the end of this run; otherwise these are the commands (from `vnit-chatbot-v2/pipeline`, Git Bash; each resumes where it stopped):
  ```
  export AGENT_MODEL=qwen/qwen3.8-27b GENAI_MODEL=qwen/qwen3.8-27b
  export GENAI_API_KEY=$(head -1 ~/groq-key.txt | tr -d '\r\n ')
  python check_answers.py --set agentic --config agent_v2_dev --pause 30 --resume
  python check_answers.py --set regression --config agent_v2_dev_regression --pause 30 --resume
  AGENT_V2=off python check_answers.py --set regression --config agent_v1_dev_regression --pause 30 --resume
  python v2_table.py
  ```

The dev model is not the final model: these runs show that the agent works, not the final score.

**Cost and speed so far:**

| | Questions | Avg tokens | Avg seconds | Avg tool calls | Avg LLM calls |
|---|---|---|---|---|---|
| v1, saved 105-case run (gpt-oss-120b) | 103 through the agent | 4,541 (median 3,625) | 24 | 0.3 | 1.3 |
| v2, Step 2-5 trials (dev model) | 13 through the agent | 12,036 (median 13,329) | 121 | 1.8 | 3.2 |
| v2, agentic set so far (dev model) | 2 | 16,008 | 160 | 3.0 | n/a |

Not like for like (different models; the trials were mostly multi-part questions, against v1's mix of mostly single facts), which is why the regression spread is being asked through both on the same model. A simple question costs about the same in both (the Registrar question: 4,169 tokens and 7 s on v2). On the hard ones, v2 is about 2.6× v1.

**Decision on the budget.** The runbook's rule is "more than 2× v1's tokens **on the original cases**". The only figures above 2× tonight come from multi-part questions on another model, and on a single-fact question v2 costs the same as v1. So the defaults stay (`AGENT_V2_MAX_STEPS=6`, `AGENT_V2_BUDGET=14000`) until the regression spread has run through both v1 and v2 on the same model (`python v2_table.py`). If v2 is then above 2× v1, set `AGENT_V2_BUDGET=10000` (about two rounds instead of three). Recorded in PROGRESS-11 too.

**EXPERIMENTS-LOG.md §37 "Agent v2"** added in the worktree.

**Done when:** no-key checks pass; the agentic and regression runs recorded or their commands written; the cost table in REPORT11; §37 added. **Met**: the dev model's allowance limits how much of the live runs completes tonight, and the commands above finish them.

## Step 10. Docs, the merge plan and the morning report

- `README.md`: a "Version 2" section near the top (what it adds, how to start it, the honest note about the model); the test count 112/112.
- `APPLICATION.md`: §5b "Agent v2" (memory, the loop compared with v1's in a table, the tools, task types, languages, streaming, the chat page and widget, the fake LLM); the new switches in §9 (`AGENT_V2`, `AGENT_V2_MAX_STEPS`, `AGENT_V2_BUDGET`, `LIVE_PAGES`, `AGENT_FAKE_LLM`); the test count.
- `HOW-TO-RUN.md`: §2a "Start version 2" in the same plain style, with the 6-click demo, the allowance warning and how to rehearse without any AI; the test count; the new files in the folder table.
- `start_chatbot_v2.bat` (port **8001**, opens `http://127.0.0.1:8001/`) and `start_website_v2.bat` (opens `/site/`), both with a commented line to switch to the dev model while the ablations run.
- `ablation_table.py`: an "agent v2" row (`answer_check_agent_v2.json`), for the merge plan.
- The merge plan and the morning report: at the top of this file.

**Done when:** docs and launchers exist, PROGRESS-11 has every step marked, the last commit is on `agent-v2`. **Met.**

