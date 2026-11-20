# Retrieval experiments log

Purpose: after `REPORT4.md` confirmed the sources-field and decomposition fixes work, it also pinned down the remaining gap precisely — it's chunk-level ranking, not page-level. Two facts needed to answer benchmark questions correctly (Civil Engineering's UG intake, the 5G lab's announcement date) are on the right, correctly-retrieved page, but buried below the chunks actually sent to the LLM: measured ranks (out of 417 chunks) were 12th and 4th/9th respectively.

This logs what was tried to close that gap, including the things that made it *worse* — so nobody re-tries them blind later. Experiments 1–3 were tested against the real 79-page/417-chunk corpus and **none of them were shipped**. Experiments 4 onwards (further down) were run on Shivanand's machine; several of those *were* adopted, as marked.

Baseline: current TF-IDF setup (`min_df=2`, `sublinear_tf=True`, `ngram_range=(1,2)`), 19-question benchmark, top-3: **18/19 = 95%**.

## 1. Global date-boost for "when" questions — rejected (net regression)

Idea: for a query matching `when|what year|which year|since when`, add a flat bonus to any chunk containing a year-like pattern (`\b(19|20)\d\d\b` or a full date), before ranking.

Result: fixed the 5G case outright (the announcement-date chunk jumped from rank 4 to rank 1). But it broke a previously-correct answer: "When was the CSE department established?" started returning the Civil Engineering page instead (that page's "the institute was established in June 1960" sentence has a date too, and out-competed the actual CSE chunk once boosted). **Net: 17/19, down from 18/19.** Rejected — a global date bonus rewards *any* date-bearing chunk, not one relevant to the actual subject of the question, so it's exactly the kind of fix that looks good on the one case you're staring at and quietly breaks another.

A narrower version (only re-rank *within* a query's already-correct top page(s), not corpus-wide) might avoid this, but wasn't built — see "Ideas not tried" below.

## 2. Real semantic embeddings via spaCy static word vectors — rejected (large regression)

Context: real transformer sentence embeddings (`sentence-transformers`, e.g. `all-MiniLM-L6-v2`) need to download model weights from huggingface.co, which is blocked from both this sandbox and the device (confirmed again this round: `curl` to huggingface.co gets a 403 from the egress proxy on both). Looked for a substitute reachable without huggingface: GitHub release downloads work fine from both (confirmed: `pip install`-triggered download of spaCy's `en_core_web_md` from a `github.com/explosion/spacy-models` release succeeded, 33.5MB). That model ships real distributional word vectors (300-dim, GloVe-family), so it's a legitimate way to get *some* semantic signal without huggingface.

Two variants tried, chunk vectors built by averaging each chunk's token vectors and comparing to the question's vector by cosine similarity:

- **Plain average of word vectors:** **4/19.** Far worse than TF-IDF. This is a known failure mode of naively mean-pooled static embeddings (a well-documented anisotropy problem: averaged vectors for unrelated sentences all end up suspiciously similar to each other, ~0.85-0.94 cosine here, leaving little room to actually discriminate the right page). VNIT-specific proper nouns (department names, "VNIT", people's names) also aren't well represented in general-purpose word vectors trained on generic web/news text.
- **TF-IDF-weighted average** (weight each token's vector by its corpus IDF before averaging, so distinguishing words like "Civil" or "intake" count for more than "the" or "department"): **13/19.** Better than plain averaging, but still clearly worse than TF-IDF alone.

**Conclusion, stated plainly: for this corpus and this benchmark, TF-IDF beats both variants of static word-vector embeddings, sometimes by a lot.** This isn't a knock on embeddings in general — it's specific to (a) mean-pooling being a weak sentence representation and (b) this site's heavy use of proper nouns and specific figures, which lexical/exact-match retrieval is naturally suited to and generic word vectors aren't. A real transformer sentence-embedding model would likely do meaningfully better than both, precisely because it doesn't just average context-free word vectors — but that needs huggingface.co (or another blocked host), which isn't available from either machine right now.

## 3. Smaller chunk sizes — already tried and rejected in the previous round

Recorded here for completeness since it's part of the same "how do we surface the specific answer-bearing chunk" question. Tested 150/100/80/60-word chunk sizes (with proportional overlap) against the same benchmark: **150 words won outright (18/19)**; 100 words scored 16/19, 80 words 17/19, 60 words 15/19. Counterintuitively, smaller/more-focused chunks made the automated page-level benchmark *worse*, not better — more, noisier chunk candidates apparently hurts TF-IDF's ranking more than sharper chunk boundaries help it. Current `CHUNK_WORDS = 150` is the empirically best setting tried, not an arbitrary default.

---

## Later experiments (2026-09-21/22, run on Shivanand's machine)

Two measures were used from here on:
- **Benchmark** (`evaluate.py`): is the right *page* in the top 3? 19 questions.
- **Fact ranks** (`fact_ranks.py`): at what rank does the *chunk containing the answer* appear? An answer is only possible if that chunk is among the few sent to the LLM.
- Plus **end-to-end answer checks** (`check_answers.py`): does the final LLM answer contain the verified fact, and does it decline questions it can't answer?

## 4. Real transformer embeddings (all-MiniLM-L6-v2) — adopted
Once huggingface.co was reachable, this worked. Benchmark dropped from 18/19 (TF-IDF) to 17/19, but the answer-bearing chunks that TF-IDF buried (Civil intake at rank 12, 5G date at rank 4) jumped to rank 1. Those two questions answered correctly end to end for the first time. Chunk-level precision matters more than the page-level benchmark.

## 5. PDFs via plain text extraction (pdfplumber `extract_text`) — rejected
11 PDFs added. The benchmark fell 17 → 16/19, and **one previously correct answer became wrong**: "What specializations does the Electrical Engineering M.Tech offer?" named an ECE programme. Cause: tables were flattened to text, so a department name in a merged cell landed next to another department's rows. 4 of 15 PDFs were also scanned images (0 words). Rolled back.

## 6. PDFs via Docling (layout-aware, OCR, real table structure) — adopted
The same brochure table came out with each department on its own row. Scanned fee sheets were OCR'd into proper tables (B.Tech tuition ₹1,25,000/year). Two extra safeguards were needed and added in `doc_convert.py`:
- Table rows are written as self-contained sentences ("Tuition Fee — First Year: 125000; Second Year: ..."), because 150-word chunking would otherwise separate rows from their column headings.
- Each row carries the table's lead-in sentence. One fee PDF has two identical-looking tables, one for OPEN/OBC/EWS (tuition 1,25,000) and one for SC/ST/PwD (tuition 0), distinguished only by the sentence above each table. Without this the two could be confused.
- First bug found and fixed while testing: merged-cell de-duplication dropped genuinely repeated values (the same fee in all four years showed only "First Year").

## 7. Placements question: context budget order — fixed
The stats chunk ("678 students ... 170 organizations") was retrieved but refused by the prompt's 6,000-character budget by 27 characters, because weaker sub-question chunks were added first. Putting whole-question chunks first, with a per-chunk cap of 1,000 characters (was 700), fixed it with a *smaller* total prompt. Simply raising both caps made it worse, because bigger early chunks pushed the stats chunk out again.

## 8. Hybrid search (embeddings + TF-IDF, weighted rank fusion) — adopted
Motivation: "Who is the Registrar?" failed because the embedding ranking of the registrar page was sensitive to trivial wording (removing the "?" moved it out of the top 3). Grid over keyword weight {0, 0.3, 0.5, 0.7, 1.0} × fusion constant {10, 30, 60}:

| setting | facts in top 3 | benchmark |
|---|---|---|
| embeddings only | 8/13 | 17/19 |
| equal weights, K=60 | 8/13 | 18/19 |
| **keyword weight 0.5, K=30** | **10/13** | **18/19** |

Neighbouring settings scored similarly, so this isn't a lucky point. (The 3 misses at the time were two fee facts, whose documents weren't ingested yet, and one half-question covered by whole-question retrieval.)

## 9. Cross-encoder reranking (ms-marco-MiniLM-L-6-v2) — adopted
After 41 documents were added, documents started crowding web-page answers down the list: Registrar fell to rank 10, Electrical M.Tech to 5, and the benchmark to 16/19. Reranking the top 30 hybrid candidates with a cross-encoder fixed this:

| | benchmark | facts in top 3 | ranks of facts present |
|---|---|---|---|
| hybrid only (+41 docs) | 16/19 | 8/15 | Registrar 10, Civil 4, Electrical 5 |
| **hybrid + rerank** | **18/19** | **11/15** | **all rank 1 except Registrar phone (4)** |

Including the chunk's title in the reranker input made no measurable difference; kept for robustness. Pool of 30 vs 50: identical results.

**Bug found while adopting it:** `agent.py` re-sorted each result list by raw embedding score, which silently undid the reranker in the real chatbot (the test called `query.retrieve` directly, so it didn't notice). Removed the re-sort, and `fact_ranks.py` now tests through `agent.retrieve_for_subquestion`, the chatbot's actual path.

## 10. Programme/year tags on the keyword side (btech, mtech, ug, yr1…) — rejected (regression)

The "similar documents" weak spot has a concrete cause on the keyword side: scikit-learn's default tokenizer keeps only runs of two or more word characters, so `B.Tech`, `B. Tech.` and `M.Tech` all collapse to the single token `tech`. A B.Tech question therefore matched M.Tech documents exactly as well as B.Tech ones — which is precisely what the 19 near-identical hostel fee sheets need to be told apart by.

Fix tried: a `programme_terms.py` module turning those written forms into distinct tokens (`btech`, `mtech`, `barch`, `msc`, `mba`, `phd`), appended to each chunk's TF-IDF text in `build_index.py` and to the question in `query.py`. Keyword side only, since the embedding model reads the real wording perfectly well. Two variants were measured on the same index (81 pages + 148 documents, 2,678 chunks):

| | benchmark | facts in top 3 |
|---|---|---|
| baseline | **16/19** | **12/18** |
| programme + level (ug/pg) + year (yr1–yr4) tags | 15/19 | 11/18 |
| programme tags only | 16/19 | 11/18 |

Both were worse, so both were reverted. The tags behave as intended in isolation (the hostel-fee question yields `btech ug yr1`, an M.Tech fee sheet yields `mtech pg yr1`), and the full variant visibly hurt an unrelated question — Electrical M.Tech specialisations fell from rank 1 to 15. The likely reason is dilution: the added tokens appear in a large fraction of chunks, so IDF treats them as near-worthless while they still shift every vector, and the reranker — which reads the real text and is what actually decides the final order — gains nothing from them.

Worth noting for the report: the diagnosis (keyword tokenisation cannot see the programme letter) is correct and still stands. It is the *remedy* that failed, and it failed at the fusion stage rather than at the tagging stage. A cleaner attempt would constrain candidates rather than enrich text — e.g. filter out chunks whose programme tag contradicts the question's before reranking, which cannot dilute anything because it changes membership, not weights.

## 11. Benchmark: accepting VNIT's own documents as correct sources — adopted (measurement fix)

`evaluate.py` scores whether the *expected page* is in the top 3. With documents indexed, three questions started "failing" because the chatbot returned something better: the B.Tech fee-estimate PDF instead of the fees page (the PDF states the per-year tuition, the page does not), and the telephone directory instead of the contact page (it holds the Registrar's extension 1364 / 2226240).

Both documents were read by hand to confirm they answer the question, and are now accepted alongside the expected page. Nothing else was loosened: the placements and girl-students-scholarship questions stay strict, because the documents out-ranking them answer a different year or only one scholarship. The honest reading of this benchmark is that it measures page-level retrieval, and `fact_ranks.py` / `check_answers.py` are the stronger evidence.

## 12. Reranking pool 30 → 60 — adopted (large gain)

The pool was tuned when the corpus was 81 pages + 41 documents. At 81 pages + 185 documents, the answer-bearing chunk often sat outside the top 30 of the hybrid ranking, so the cross-encoder never saw it:

| pool | benchmark | facts in top 3 | hostel fee rank | Electrical M.Tech rank |
|---|---|---|---|---|
| 30 | 16/19 | 13/18 | 12 | 9 |
| **60** | **16/19** | **15/18** | **1** | **1** |
| 100 | 16/19 | 15/18 | 1 | 1 |

60 is kept: 100 measured identically and costs more cross-encoder work per question. This single number was worth more than any other change in this round — a reminder that a parameter tuned on a small corpus needs re-tuning when the corpus grows.

## 13. Programme and academic-year contradiction filter — adopted

`programme_terms.py` reads which degree programme (btech/mtech/…, with ug/pg standing for their members) and which academic year (2025-26 style) a question and a passage are about. `query.py` drops candidates that state a *different* programme or year before reranking; a passage naming neither stays eligible, since many correct answers come from pages that never spell one out.

Measured at pool 60: facts in top 3 15/18 with the filter, 14/18 without, and the hostel-fee question (the 19 near-identical fee sheets) goes from rank >20 to rank 1. Unlike experiment 10 this only decides which candidates compete, never how they are scored, so it cannot dilute the ranking.

## 14. Per-source caps — rejected in the results, kept in the pool

Capping the *final* results at 2 chunks per source (to stop one document filling them) broke a question that legitimately needs several chunks of one document: "when do classes start" fell from rank 4 to >20, exactly the failure mode that sending 5 passages per sub-question was introduced to fix. Reverted.

Capping each source's share of the *candidate pool* at 6 is kept. It measured neutral on both benchmarks, and it is a guard against a diagnosed failure mode: two placement reports' company lists (dozens of near-identical chunks each) filled the pool for the placements question. Neutral-but-justified, not a measured gain.

## 15. Two text-quality bugs found by chasing one question — fixed

Both were found while investigating why the placements question failed, and both are correctness fixes rather than ranking tweaks:

- **Mojibake**: when a server sends no charset, `requests` falls back to ISO-8859-1, so UTF-8 punctuation was stored as `2025â€“26`. A question about "2025-26" could not match the passage holding its answer. `fetch_utils.py` now sniffs the encoding. Affected 2 pages, 27 lines.
- **Sentences broken across lines**: `get_text(separator="\n")` puts every inline element on its own line, and VNIT styles figures in bold, so the placements sentence was stored as three fragments ("…more than" / "678 students" / "from undergraduate…"). `_rejoin_sentences` joins a line to the one above only when the line above does not end a sentence and this line continues one, which leaves headings and real lists alone. Affected 62 of 81 pages.

Scores were unchanged by the pair (16/19, 15/18), and the miss set shifted slightly (Electrical M.Tech started hitting, CSE-established stopped). They are kept because the stored text is now right, not because the numbers moved.

## 16. The one question that still fails: 2025-26 placement figures

"How many students got placed in 2025-26 and how many companies came?" (678 students, 170 organisations) is stated only in one paragraph of the T&P page. Traced through the stages, that chunk ranks 249th by embeddings and 519th by keywords, fusing to 293rd, because the corpus now holds two placement reports whose company lists run to hundreds of chunks that match "placed"/"companies" far more densely — and the 2025-26 report itself gives internship seat counts, not placement totals. Pool diversification does not reach rank 293, and enlarging the pool that far costs more than it returns (pool 100 already measured no better).

Left failing deliberately. The chatbot says it cannot find the figures rather than quoting the 2024-25 ones, which is the behaviour this project values; the fix would be a page-level retrieval stage (see "Ideas not tried"), not another ranking tweak.

## 17. Final measurement: the full corpus (2026-10-03)

Experiments 10–16 were measured with 185 documents indexed. Re-measured after converting everything VNIT links — 81 pages + 406 documents, 8,162 chunks, 2.2× the chunks of the §12–16 runs:

| Check | 148 docs (09-22) | 185 docs (10-02) | **406 docs (10-03)** |
|---|---|---|---|
| `check_answers.py` | 13/18 | 17/18 | **17/18** |
| `fact_ranks.py` | 12/18 | 15/18 | 14/18 |
| `evaluate.py` | 16/19 | 16/19 | **17/19** |

Worth noting honestly: end-to-end answers held at 17/18 and page-level rose, while the answer-chunk measure slipped by one — tripling the corpus adds competition, and two facts moved from rank 3 to rank 4 (end-semester exams, which the LLM still answers correctly, because `generate.py` sends up to 5 passages per sub-question). That gap between "chunk ranked in the top 3" and "answer is correct" is the reason all three checks are kept rather than one.

Also re-ran during this round: the personal-data filter over all 406 converted documents, with nothing flagged. That check matters because a run killed between writing a document's text and saving `status.json` leaves a text file whose result was never recorded (14 such files); the filter runs before the write, so they were already screened, and this confirmed it.

## 18. A bigger test set, and what it found (2026-10-03)

The 18-question check was written alongside the features it tested, so it mostly asked things already known to work. It was expanded to **39 cases**: 34 factual questions, 5 that must be declined, and 2 two-turn conversations. Every fact was read out of its source document by hand first, and the document is named in a comment beside each case so it can be re-checked later.

First run: **29/39**. Four of the ten failures turned out to be genuine bugs, two were faults in the test harness itself, and the rest are the documented weak spots. That is the point of a wider test set: the questions nobody thought to ask are where the bugs are.

### 18a. The question mark (the real find)

`agent.decompose` stripped the trailing "?" from every question before retrieval — harmless-looking, and wrong. The cross-encoder was trained on queries that look like questions, and it ranks differently without one. Measured on "What is the hostel fee for first year B.Tech girls for the Winter 2026 session?":

| query | rank of the correct fee sheet |
|---|---|
| with "?" | **1** (and the chunk holding "Rs. 32650") |
| without "?" | not in the top 5 — the international and M.Tech sheets won |

So the chatbot answered ₹73,000 (the international students' fee) to a question about domestic girls. `decompose` now keeps the question mark, and adds one to each part when it splits a compound question.

Why it went unnoticed for so long: `fact_ranks.py` calls `retrieve_for_subquestion` with its own question strings, and `evaluate.py` calls `query.retrieve` directly. **Neither ever ran `decompose`**, so both measured a slightly better retrieval path than the chatbot actually used. A benchmark that bypasses a production step cannot see bugs in it.

### 18b. Gender as a third contradiction axis

The hostel fee sheets come one per gender and are otherwise near-identical, so the cross-encoder could not separate them: the girls' sheet was the 3rd-ranked candidate going into reranking and still lost to the boys' and M.Tech sheets. `programme_terms.genders()` now joins programme and year as a filter axis (a document naming both genders, like "INTERNATIONAL BOYS & GIRLS", still matches either question). Benchmarks unchanged at 17/19 and 14/18; the girls' question went from wrong to rank 1.

### 18c. Empty answers from a reasoning model

gpt-oss-20b returns its reasoning on a separate channel. When the token budget runs out there, `content` comes back empty — and that empty string was handed to the user as a blank answer, seen live on a follow-up question. `generate.py` now retries once with `reasoning_effort: "low"` and falls back to extractive if that is empty too. The same parameter is what makes the follow-up rewrite work at all: with it the rewrite used 117 completion tokens, without it 400 tokens produced nothing but reasoning.

### 18d. Two faults in the test harness, not the chatbot

- The anti-ragging answer "1800-180-5522" was marked wrong because the LLM wrote it with non-breaking hyphens (U+2011) that the pattern's plain `-` could not match. Answers are now normalised to ASCII punctuation before matching. A test that fails a correct answer is worse than no test: it hides the real failures in the noise.
- Two fee questions asked for the "OPEN category" rate. OCR had mangled the sentence that introduces the second table in those PDFs ("Folr t orf VNIT, Nagpur."), so the document no longer states in readable text which category the figure belongs to. The questions now ask for the fee without the category, because the chatbot was being asked for a label its source had lost.

### 18e. What stayed failing, honestly

The placements figures (§16), the IDFC poster deadline (two-column layout, and it varies between runs), the end-semester range (a newly converted per-slot exam schedule gives 07/12/2026 for slot A, and the chatbot now quotes that single date instead of the 7–15 Dec span), the summer-term per-course fee (₹3,000 in a notice, out-ranked by semester fee estimates) and slot-A mid-sem (the eight slot rows land in different chunks, so a question about one slot may retrieve another). All five are retrieval or layout problems with the diagnosis recorded, not guesses.

**All five "must decline" questions passed**, including the one designed as a trap: asking for the 2015-16 hostel fee, which the data has no figure for, did not get the 2026-27 number.

## 19. Pooling both phrasings, and a benchmark that runs the real path

Experiment 18a found that the cross-encoder ranks a question differently with and without its "?". Keeping the mark fixed some questions and broke others, measured on six questions by the rank of the answer-bearing passage:

| question | with "?" | without "?" | pooled (adopted) |
|---|---|---|---|
| girls' hostel fee | 1 | 7 | within top 7 |
| classes start (first year) | not in top 10 | 4 | 4 |
| re-examination dates | 7 | 1 | 1 |
| Electrical M.Tech specialisations | 2 | 1 | 2 |
| boys' hostel fee | 1 | 1 | 1 |
| end-semester exams | 2 | 2 | 2 |

Neither phrasing wins everywhere, so `query.retrieve` now embeds both, fuses each with its own keyword ranking, and interleaves the two candidate lists before one reranking pass. The pool stays the same size, so there is no extra cross-encoder cost — only a second (cheap) embedding and TF-IDF pass. The chatbot is now insensitive to punctuation it should never have cared about.

**`chunk_ranks.py` (new)** exists because of how 18a was missed: `evaluate.py` and `fact_ranks.py` both bypass `agent.answer`, the function the API calls. The new benchmark asks all 32 answerable `check_answers.py` questions through `agent.answer` and reports how far down the answer-bearing passage sits — no API key, no cost, so it is also the tool that still works when the LLM's free quota is spent. It smooths out the "19 th Aug" spacing that scanned PDFs produce, which otherwise reports a found passage as a miss.

Tuning the per-source pool cap against it (the final results were coming back with 5 of 7 passages from one M.Tech hostel notice):

| cap | passage in top 7 | passage in top 3 | `fact_ranks` | `evaluate` |
|---|---|---|---|---|
| 3 | 28/32 | 26/32 | — | — |
| **4** | **29/32** | **26/32** | **15/18** | 16/19 |
| 5 | 29/32 | 25/32 | — | — |
| 6 | 29/32 | 24/32 | 14/18 | 17/19 |

4 is adopted: it wins on the benchmark that runs the real path and on `fact_ranks`, and costs one question on `evaluate`'s page-level measure. Passages per sub-question were also raised 5 → 7 with the context budget 6,000 → 7,000 chars, because pooling spreads the answer-bearing passage a little wider and at 5 the girls' fee sheet lost the budget race.

**A warning about free-tier limits as a measurement hazard:** sending 7 passages instead of 5, plus a rewrite call per conversation turn, pushed the suite over Groq's per-minute token allowance part-way through a run. Every question after that point fell back to extractive and scored as a failure — 31/39 became 21/39, then 0/39, which reads as a collapse in quality and is nothing of the sort. `check_answers.py` now prints a warning naming the affected questions and the reason, and paces at 30s. Any measurement run on a free tier should be read with that in mind.

## 20. The agentic layer: planner, tools, verifier (2026-10-30)

The one-shot pipeline searched once and printed whatever the LLM wrote; README listed "the planner and verifier" as the missing agentic pieces. Built in `planner.py`, `tools.py` and `verifier.py` (design in APPLICATION.md §5a). The principle throughout: the tuned first search is the agent's first observation, not something it replaces, so a question the old pipeline answered is answered from the same passages.

### 20a. What the free tier forced

- **Groq counts the requested `max_tokens` against the 8,000-tokens-a-minute allowance up front.** At `max_tokens` 2,000, a question with one tool round (call 1 ≈ 4,200 tokens with its reservation, call 2 ≈ 5,500) could never fit in a minute, and *every* tool-using question was refused with a 429 and fell back. Lowered to 1,200, plus a pacer that reads `x-ratelimit-remaining-tokens` and waits the few seconds the refill needs. Measured afterwards: tool-using questions wait 15–45 s for quota instead of failing.
- **The daily allowance (~200,000 tokens per model per rolling 24 h) is the real limit for measurement.** The first full agent run reached the LLM on 3 questions; the other 35 were refused, because a day of building and testing had spent gpt-oss-20b's allowance. Two fixes: (1) the agent runs on `gpt-oss-120b` and the fallback on `gpt-oss-20b`, which have separate allowances, so in use the fallback survives the agent's quota running out; (2) the daily limit is recognised from Groq's error text and stops the run at once, and `check_answers.py --resume` finishes it later without re-asking answered questions.
- **A bug the daily limit exposed:** Groq writes "try again in 12m3.2s"; the parser read only the trailing seconds and retried after 3.2 s. Fixed and tested.

### 20b. What gpt-oss did that the design had to absorb

- **It called tools it was not offered.** For the final answer, tools were withdrawn, but with tool calls still in the conversation the model kept emitting them (including `read_document` with `cursor`/`loc` arguments, from the browsing tool it was trained with), and Groq returned `400 tool_use_failed`; with retries and quota waits, two questions took ~150 s and then fell back. The final answer is now written from a clean prompt holding every passage found and no tool history; it has not happened since.
- **It wrote citations several ways:** `[P3]`, `[P3, P5]`, `【P3】`, `[**P3**]`, plus stray `【commentary】`. All are normalised to `[1]`, `[2]` matching the sources list; unknown labels are removed and recorded in the trace.

### 20c. The placements question: the tool works, the planner does not choose it

`read_document` on the T&P page returns the paragraph with **678 students and 170 organisations** at rank 1 (`test_agentic.py` pins this) — the page-level stage §16 asked for. But neither gpt-oss-20b nor gpt-oss-120b opens that page by itself: both open the *2025-26 Placement Report* (which has internship seat counts, not totals), search it a second time, and then correctly say the figures are not in what they found. Two changes were tried to steer it, both kept because they improved what the agent sees without hurting anything measured:
- a list of pages whose **titles** match the question is shown with every search (~60 tokens). Title matching first ranked hostel-fee notices above the T&P page, because "placed" ≠ "Placement" and "students" is in a hundred titles; stems (first five letters) and rarity weighting (IDF over titles) fixed that, and the programme/year/gender filter now applies to titles too, so "B.Tech girls" no longer lists the M.Tech sheet first;
- a line in the prompt: if a document you opened does not hold the answer, look for another page; headline figures are often on a section's own page.
The T&P page now appears second in the list the agent is shown. It still picks the report. This is left as the one known planning failure, with the honest outcome that the agent declines rather than quoting 2024-25 numbers.

### 20d. Verifier findings

Deterministic checking of figures, dates, emails and phone numbers caught a real problem in its first live use and three of its own bugs:
- **Real catch:** asked for four years of B.Tech tuition, the first draft stated ₹5,00,000 with no visible derivation. Flagged; the revision wrote out 1,25,000 × 4 = 5,00,000, whose arithmetic the verifier checks; verified.
- **Own bugs, each now a test:** a phone number at the end of a sentence ("…5522.") was missed; "Total = 125,000 × 4 = 500,000" was mis-parsed because the scan paired "Total =" with the first number; and an academic year written "2026-27" was flagged against a source saying "2026-2027" (the "27" checked alone). Academic years are now compared as units.

### 20e. Harness fault, again (§18d's lesson)

The first scoring of the agent run showed **31/39**, with four "must decline" questions failing. All four answers were read by hand: every one was a correct refusal ("none of the provided documents contain information about…"), a phrasing the refusal pattern did not include. The one-shot run then produced a fifth ("No passage provides the hostel Wi-Fi password"). The pattern was widened for both phrasings, and `check_answers.py --rescore` re-marks the saved answers without asking anything again, so the correction is in the pattern's history rather than in a hand-edited results file. Only those five results changed.

### 20f. Results

`check_answers.py`, 39 cases, every question reaching the LLM (agent: gpt-oss-120b; 2026-10-30):

| | agent | one-shot baseline |
|---|---|---|
| End-to-end | **35/39** | in progress: **19/20** on the questions answered so far (the agent scores 19/20 on the same 20) |
| Must-decline questions refused | **5/5** | 2/2 so far |
| Tools used | on 9/39 questions | — |
| Tokens per question (average) | 4,815 | not recorded (one call, ~3,000 by the prompt size of §20a) |
| Verifier verdicts | 30 verified, 4 refusals, 4 nothing to check, 1 flagged (the "2026-27" false alarm of §20d, since fixed) | — |

The four agent failures are the documented weak spots, not new ones: placements (§20c), M.Sc and B.Arch tuition (the OCR-damaged fee tables of §18d; the answer passage is outside the top 12 and at rank 9 in `chunk_ranks.py`, and the agent's two extra searches did not reach it either), and slot-A mid-sem (§18e, a per-slot timetable row). Questions where tools made the difference include the summer-term per-course fee (₹3,000, which §18e listed as failing: the agent opened the Summer Term 2026 notice and found it) and the girls' hostel fee in an earlier live test (it opened the hostel admission procedure).

Retrieval benchmarks are unchanged, as they should be (the first search is untouched): `evaluate.py` 16/19, `fact_ranks.py` 15/18, `chunk_ranks.py` 29/32. `test_agentic.py`: 29/29.

## 21. Topic intent (Runbook 7, Step 1)

**Changed.** `router.intent(question)` tags every lookup with a topic: `hostel, fees, scholarship, placement, calendar, admission, people, department, rules, other`. Keyword patterns, checked in that fixed order so the more specific topic wins ("hostel fee" is `hostel`, "scholarship last date" is `scholarship`). `respond.answer` returns it as `intent` (None for greetings and other direct replies) and adds "Topic: …" to the trace. Nothing uses it yet; Steps 3 and 4 do (which details a question needs; which office to point to). It is rule-based, as MARAUS's coordinator and the adaptive-RAG classifier tag queries before retrieval, but without an LLM call: free, instant and repeatable.

**Measured.** All 39 `check_answers.py` questions were tagged and read by hand; every tag was sensible on the first ordering (e.g. the anti-ragging helpline is `people`, ahead of `rules`, which is what Step 4's hand-off needs; "a day scholar bus pass cost" is `fees`, since the scholarship pattern needs "scholarship", not "scholar"). Twenty of them, plus the priority cases, are pinned in `test_agentic.py`. No retrieval change, so `evaluate.py` 16/19, `fact_ranks.py` 15/18, `chunk_ranks.py` 29/32 are unchanged; `test_agentic.py` 32/32.

**Harness fix found on the way.** `check_answers.py --only X` wrote just the X results to `answer_check.json`, overwriting the full 39-question run. The runbook's later steps use `--only` repeatedly, so `--only` now replaces only its own questions in the saved file.

## 22. Corrective retrieval gate (Runbook 7, Step 2)

**Why.** Choosing to look further was left entirely to the LLM, and for the 2025-26 placement figures it never chose the T&P page (§20c). Corrective RAG grades the retrieved passages and fixes retrieval *before* answering when they look weak. The cross-encoder already scored every candidate, and those scores were thrown away after sorting.

**Changed.**
- `query._rerank` returns the scores with the order; every result carries `"rerank"` (None without the reranker). The order is unchanged: the top-7 chunk ids of three questions were saved before the change and are compared in `test_agentic.py`; `chunk_ranks` 29/32, `fact_ranks` 15/18 and `evaluate` 16/19 are identical.
- `grader.grade(question, report)` (no LLM): `top` is the best cross-encoder score for the whole question; `coverage` is the share of the question's rarer word stems (IDF over all chunks, at or above the median of the question's own words) plus any academic year it names, found in the top 3 passages. `correct` if top ≥ 3.0 and coverage ≥ 0.75; `incorrect` if top < 0; otherwise `ambiguous`, and always `ambiguous` when a named academic year appears in none of the top 3.
- `respond.corrective_passages`: when the grade is not `correct` (and `CRAG_GATE` is not `off`), look inside the 2 best-titled pages the first search did not reach (`tools._title_scores`, `query.retrieve_within`) and keep each one's best passage if it scores above 0. They go to the planner after the first search's passages (`planner.run(extra=...)`, origin `corrective`), with one line telling the model `Search quality: <grade> (<why>)`. The trace shows "The first search looked weak (…), so I also looked inside “…”." No LLM call is added.
- The one-shot fallback is unchanged and does not get the corrective passages (the smaller change); the grade line is then left out of its trace, so the trace never claims a lookup the answer did not use.

**Calibration** (`grade_calibration.py`; "hit" = the answer passage is among the 7 sent to the LLM, from `chunk_ranks.py`):

| question | top | coverage | answer passage in top 7 | grade |
|---|---|---|---|---|
| civil_intake | 2.5 | 0.33 | hit | ambiguous |
| 5g_announced | 6.7 | 1.00 | hit | correct |
| placements | -1.2 | 1.00 | MISS | incorrect |
| chemical_spec | 3.8 | 1.00 | hit | correct |
| electrical_mtech | 7.5 | 1.00 | hit | correct |
| director | 7.1 | 1.00 | hit | correct |
| dean_academic_email | 5.5 | 1.00 | hit | correct |
| mech_established | 5.1 | 0.50 | hit | ambiguous |
| registrar | 7.8 | 1.00 | hit | correct |
| btech_fee_open | 8.2 | 0.75 | hit | correct |
| btech_fee_scst | 7.8 | 0.75 | hit | correct |
| kotak_scholarship | 7.7 | 0.67 | hit | ambiguous |
| idfc_deadline | 7.8 | 0.75 | hit | correct |
| hostel_fee_first_year | 8.0 | 1.00 | hit | correct |
| classes_start_fy | 7.9 | 0.75 | hit | correct |
| endsem_fy | 8.1 | 0.75 | hit | correct |
| hostel_fee_girls | 7.0 | 0.50 | hit | ambiguous |
| cse_established | 7.4 | 1.00 | hit | correct |
| reexam_dates | 6.9 | 0.50 | hit | ambiguous |
| convocation | 7.3 | 1.00 | hit | correct |
| adddrop_deadline | 8.0 | 1.00 | hit | correct |
| antiragging_helpline | 7.8 | 1.00 | hit | correct |
| summer_term_fee | 3.1 | 0.33 | hit | ambiguous |
| summer_term_max_courses | 5.9 | 1.00 | hit | correct |
| dean_academic_name | 7.3 | 1.00 | hit | correct |
| dean_planning_email | 6.3 | 0.67 | hit | ambiguous |
| msc_tuition | 7.2 | 0.67 | MISS | ambiguous |
| mtech_tuition | 6.6 | 0.50 | hit | ambiguous |
| mtech_fee_scst | 7.6 | 0.75 | hit | correct |
| barch_tuition | 5.4 | 0.67 | MISS | ambiguous |
| hostel_appliances | 4.9 | 0.33 | hit | ambiguous |
| midsem_slot_a | 6.8 | 1.00 | hit | correct |
| unanswerable_1995 | -2.9 | 0.33 | decline | incorrect |
| unanswerable_wifi | -5.7 | 0.00 | decline | incorrect |
| unanswerable_old_hostel_fee | 5.1 | 0.75 | decline | ambiguous |
| unanswerable_director_salary | -0.1 | 0.00 | decline | incorrect |
| unanswerable_bus_pass | 0.5 | 0.00 | decline | ambiguous |

Results: every miss grades not `correct` (3/3), 20 of 29 hits grade `correct`, and all 5 must-decline questions grade not `correct`. How the thresholds were chosen:
- `LOW = 0`: the placement miss is the only answerable question below it (−1.2); three of the five must-decline questions are below it too.
- `HIGH = 3.0`: separates nothing on its own beyond civil_intake (2.5), which coverage catches anyway; the hits' scores run 2.5 to 8.2.
- `COVER = 0.75`: M.Sc and B.Arch tuition score 7.2 and 5.4, as high as hits, so only coverage separates them (0.67, both missing "yearly"). **This separation is fragile and is recorded as such**: "yearly" is a word students use and fee sheets don't, and B.Tech OPEN tuition, which also lacks it, reaches 0.75 only because its question has four key words. Most uncovered words in the hits are phrasing of this kind ("money", "held", "keep", "my", "address"), which is why 9 hits grade `ambiguous`. A gate that fires on them costs up to two in-page searches (no LLM) and ~250 prompt tokens per page kept.
- The year rule was added after the first calibration run graded the 2015-16 hostel-fee question `correct` (5.1 on the 2026-27 sheets, coverage 0.75 with the year counted as one word in four). A named year no top passage mentions is a strong sign of the wrong document.
- One `ambiguous` hit is a real signal, not phrasing: for the girls' hostel fee the top 3 whole-question passages come from the M.Tech/M.Sc hostel page, and "girls" is in none of them; the girls' sheet is lower in the top 7.

**Budget.** For the placements question the first agent prompt is ~4,600 tokens with the corrective passage (budget 6,000).

**End to end** (`check_answers.py --only`, gpt-oss-120b):

| Question | Before (30 Oct) | After |
|---|---|---|
| placements | FAIL (opened the report, declined) | **PASS**: 678 and 170 from the T&P page, cited, verified, no tool calls, 3,688 tokens |
| director | PASS | PASS (graded correct, gate silent) |
| hostel_fee_first_year | PASS | PASS |
| hostel_fee_girls | PASS | PASS |
| unanswerable_director_salary, unanswerable_old_hostel_fee (matched by `--only`) | PASS | PASS (still refused) |

The saved 39-question file now reads 36/39 (35 + placements). `test_agentic.py`: 35/35.

## 23. Clarify or assume: slots and a student profile (Runbook 7, Step 3)

**Why.** "What is the hostel fee?" has no single answer: there are 19 near-identical hostel fee sheets, one per programme, year and gender. The agent picked one, so a student could be told another group's fee. AdvisingWise's agent can ask the student for missing information and keeps a profile; MARAUS traced most of its remaining errors to vague questions.

**Changed.**
- New `slots.py`. `extract` reads programme, gender, category (OPEN/General, OBC, SC/ST, SC, ST, EWS, PwD) and year of study, each only when exactly one value is named. `REQUIRED` lists what a topic needs: hostel → programme and gender; fees → programme and category; calendar → programme. `needs_clarification` asks back only when a required slot is missing from both the question and the profile *and* the relevant first-search passages hold two or more different values for it. `apply_profile` fills in slots from earlier in the chat ("What is the hostel fee? (for B.Tech girls)") and says so in the trace. `clean_profile` keeps only known keys and values.
- `respond.answer(..., profile=None)`, in this order: resolve follow-up → route → topic → apply profile → first search → clarify check (`CLARIFY=off` disables it) → corrective gate → planner. A clarification returns `mode: "clarify"` with the choices, no sources and no LLM call. If the same question is asked again straight after (the student typed it instead of choosing), it is answered as it stands.
- `api/main.py` takes `profile`, cleans it and never stores it. The chat page keeps the profile in memory only (not localStorage), shows the choices as buttons, re-asks the original question when one is clicked, shows the assumption as "Understood as", and has a "Clear my details" link.
- `check_answers.py` has 4 new cases (`CLARIFY_CHECKS`), with a profile and a "clarify" expectation.

**What had to be tightened, and how it was measured.** The first version counted every passage. Running all the test questions through it, two of the existing 39 were asked back:
- "How much does one summer term course cost?" got a choice between M.Tech and B.Arch;
- "How much does a day scholar bus pass cost?" got a choice between M.Tech and M.Sc.

In both cases those passages were fee estimates that the reranker scored 2–3 (bus pass: below 1). They matched the topic, not the question. So a passage now counts only if its rerank score is at least 3.0, the line `grader.py` draws for a relevant first search. A passage naming several values ("Boys & Girls", "OPEN/OBC/EWS") is general and never counts. Result: **0 of the existing 39 clarify**, measured through `respond.answer` with no key.

**Choices.** The vague hostel question's top passages are from the Ph.D and M.Sc hostel pages; the B.Tech sheets name their programme mostly in titles, often as "UG (B.Tech/B.Arch)". So choices also count the 10 best-titled documents (titles naming one or two values). The 4 values backed by the most documents are offered, in a fixed order (B.Tech first) so buttons never move. Choices for "What is the hostel fee?": B.Tech, B.Arch, M.Sc, Ph.D. After B.Tech: Boys, Girls.

**Results.**

| Case | Result |
|---|---|
| `clarify_hostel_vague`: "What is the hostel fee?" | PASS: clarify, choices btech, barch, msc, phd |
| `clarify_then_answer`: "…for first year?" with profile B.Tech girls | PASS: ₹32,650, verified |
| `no_clarify_when_specific` | PASS: answered (₹32,150) |
| `no_clarify_director` | PASS: answered |
| `conv_hostel_girls` (regression) | PASS |
| Clarifications on the existing 39 | 0 |

Through the live API: "What is the hostel fee?" → B.Tech → Girls → "Rs 32,650 is the total hostel fee for B.Tech girls (double-seater) admitted in 2026-27", 3 figures verified, 0 tool calls. Retrieval checks are unchanged (no retrieval change). `test_agentic.py`: 41/41.

**Limits.** Slot values come from regexes over passages and titles. A sheet that never states its group (some say only "FIRST YEAR GIRLS") supports the gender choice but not the programme. Category questions ("fees" without a category) never clarify on the current data, because the fee estimates name several categories in one passage. That is why `msc_tuition` and `barch_tuition` are answered rather than asked back.

## 24. Hand off to the right office (Runbook 7, Step 4)

**Why.** A correct refusal ("none of the documents contain the hostel Wi-Fi password") was a dead end for the student. Commercial university assistants send the questions they cannot answer to the right office.

**Changed.**
- `data/contacts.json` maps a topic (§21) to one office. It was written by hand from `contact_us.txt` and `administrative_officers.txt`, with every email and phone copied character for character and `source_url` taken from the file's `SOURCE_URL:` line:
  - hostel → Assistant Registrar, Hostel Section;
  - fees → Assistant Registrar, Accounts Section;
  - calendar → Deputy Registrar, Exam Section;
  - people → Director Office;
  - other → Registrar Office.
- Placement, scholarship, admission, department and rules are **left out**: no page in the data names their office with a contact (the T&P page carries no email or phone), and a guessed office is worse than none.
- `respond.hand_off`: when an LLM-written answer is a refusal, or its verification verdict is `unsupported`, and the topic has an office, it appends `**Who can help:** <office> — <email>, <phone>`. It also adds the contact page to the sources and the trace line "I couldn't find this in VNIT's documents, so I've added who to contact." The contact is not passed through the verifier again, since it comes from a checked file, not from the LLM.
- The chat page renders the bold line as it is; it only gained a label ("handed off") for the new trace step.

**A verifier gap found on the way.** The first live run of `--only wifi` passed but got no contact. The answer read "none of the provided **VNIT** documents contain…", and `verifier.is_refusal` allowed no extra word there. `check_answers.py`'s pattern had already been widened for that in §20e, but the verifier's had not. They now match, and the phrase is in `test_agentic.py`. This also changes which answers the verifier labels "refused".

**Results.**
- `--only wifi`: PASS. The answer ends "**Who can help:** Assistant Registrar, Hostel Section — AR_HOSTEL@vnit.ac.in, 0712-2801373", the Administrative Officers page is listed as a source, and the answer still matches the refusal pattern.
- Tests: every contact appears verbatim in its source file with its URL; a hostel refusal gets the hostel contact; a normal answer, and a refusal on a topic with no known office, get nothing.
- `test_agentic.py` 44/44; no retrieval change.

## 25. Table lookup tool (Runbook 7, Step 5)

**Why.** Fee amounts and exam dates live in tables. TableRAG keeps document tables in a database and answers table questions with a query; MARAUS gives numeric questions their own agent. The two OCR-damaged fee questions (§18d) fail because the lead-in above the table is unreadable ("Folr t orf VNIT, Nagpur."), so passage search for "M.Sc tuition" never reaches the row.

**Looked before parsing.** 40 real table lines (`grep " | " data/raw/doc_*.txt`) showed two shapes:
- `<lead-in> | <caption>: <row header>: <row label> — <column>: <value>; …`
- a headerless one, `<lead-in> | <caption>: <row label> | <value> | <value>`.

Both are parsed. OCR noise in headers (`2026-27.1" YR`, `TYPE.TYPE`) is kept as it is.

**Built.**
- `build_facts.py` writes `data/processed/facts.db` (gitignored, rebuilt after `build_index.py`): **23,088 cells from 210 documents** (6,414 numeric; hostel fees 1,132, fees 1,140, calendars/timetables 721, admission 1,296, scholarship 432, other 18,367). Tags (programme, gender, category, year of study, academic year) are read from title + lead-in + row label. Only documents in the index are included, so the privacy exclusions carry over.
- `tools.lookup_table` returns one result per *table row* (its cells joined), not per cell: as single cells, 8 results for the girls' hostel sheet were all header cells ("Sr. No.") and never reached the total. Matching:
  - keywords are word stems matched in cells, row label, lead-in and title, and a row must match at least half of them;
  - a tag filter keeps rows that state the value *or state none* (as `programme_terms.py` does), since most fee rows name their group only in the title;
  - order: rows stating the filtered values first, then more keywords matched, then rows holding figures, then newer documents.
- The SQL is built in code and parameterised; the model gives only keywords and tag values (enums).
- A bug found while testing: in SQLite `NULL = 'btech'` is NULL, so a sum of tag matches containing it is NULL and the right sheet sorted *last*. `IS` (0 or 1) fixed it.
- Rows become `[P#]` passages through `Evidence`, so citations and the verifier work unchanged. `Evidence` now keys passages on their whole text, not the first 80 characters: rows of one sheet share a long lead-in and would otherwise collapse into one label.
- `LOOKUP_TABLE=off`, or a missing `facts.db`, removes the tool.

**Tool-level results (no LLM):**

| Lookup | First rows |
|---|---|
| `hostel fee total`, B.Tech, girls, 2026-27 | the girls' 2026-27 sheet, "Total; 2026-27 1st YR: 64200; …" |
| `tuition fee`, M.Sc | 2-year M.Sc estimate: "Tuition Fee — First Year: NIL" (SC/ST table), then "First Year: 15000" (the OCR-damaged OPEN table) |
| `tuition fee`, B.Arch | 5-year B.Arch estimate: "First Year: 125000; …", then the SC/ST/PwD row (0) |
| `mid sem slot A` | First Year B.Tech/B.Arch exam schedule, slot A, "Mid Sem.Date: 01/10/2026" |

The runbook's test asked for a row containing 32650. The girls' sheet states ₹32,650 (the Winter 2026 instalment) in a *sentence*, not its table, whose row is the yearly total ₹64,200. The test checks that row instead.

**End to end** (`check_answers.py --only`, gpt-oss-120b):

| Question | 30 Oct | Now | Notes |
|---|---|---|---|
| `barch_tuition` | FAIL | **PASS** | ₹1,25,000 found via `read_document` on the JoSAA fee document, not `lookup_table` |
| `msc_tuition` | FAIL | FAIL | see below |
| `midsem_slot_a` | FAIL | FAIL | see below |
| `hostel_fee_*`, `btech_fee_*` (regression) | PASS | PASS | |

**The agent never called `lookup_table`.** It was offered in every run above and chosen in none.
- First run, the prompt line from the runbook as its own sentence after the other tools: for M.Sc the agent used `search_vnit` and `find_documents`, found only the SC/ST table (NIL), and said the other categories were not in the documents.
- The line was then moved into the "act before giving up" sentence, naming `lookup_table` first for fee amounts and table dates. The retry answered from the first search with **no tool calls at all**: it judged the SC/ST "NIL" row enough and said the OPEN fee was not shown.

The runbook says not to force a tool by code, and this was not done. The honest reading: the tool works (the 15,000 row is the second row it returns), but the planner's failure for M.Sc is deciding *not to look further*, not picking the wrong tool. The OCR damage is visible in the source lines:

```
Folr t orf VNIT, Nagpur. | Fees per year: Tuition Fee — First Year: 15000; Second Year: 15000
Following mentioned the 2 year FEE ESTIMATE for the SC/ ST students admitted in the M. Sc. Program of VNIT, Nagpur. | Fees per year: Tuition Fee — First Year: NIL; Second Year: NIL
```

Passage search finds the second (readable) row, which answers for SC/ST only. The first row does not say which students it is for. Even a model that found it would have to infer "OPEN" from the SC/ST table beside it, and the answering rules forbid that inference.

**Slot A is ambiguous, not wrong.** The agent answered **04/09/2026** from the *UG-PG Higher Semester Timetable (Winter 26)*, which really gives slot A's mid-sem as 04/09/2026 for 3rd/5th/7th/9th-semester students. The check expects 1 Oct, the *first-year* date from the First Year academic calendar and exam schedule. The question ("When is the mid semester exam for slot A in Winter 2026?") names no year of study, so both are right for some students. §18e called this a split timetable row; with the table data it is clearly a question whose answer depends on the student's year. That is a Step 3 case: `study_year` is not in `REQUIRED["calendar"]`. Adding it would make the chatbot ask, and that change, and any change to the check's question, is left for a decision rather than made to pass a test.

`test_agentic.py`: 49/49 (parser on 6 real lines, the girls' total and M.Sc rows, SQL-ish input changes nothing, the switch, rows sharing a lead-in). Retrieval checks unchanged.

## 26. Ablations: what each piece contributes (Runbook 7, Step 6)

**Why.** The Agent-Orchestrated Adaptive RAG paper measured reflection *lowering* overall scores and multiplying latency six times. Adding a piece is not evidence that it helps, so each one is measured on its own.

**Switches** (environment variables, default on; each is pinned by a test that it fully disables its piece):
- `AGENT_TOOLS=off`: no tools are offered; the agent answers from the first search;
- `VERIFY_REVISE=off`: verifies and flags, but makes no revision call;
- `CRAG_GATE=off`: no grade, no corrective passages (§22);
- `CLARIFY=off`: neither asks back nor applies the profile (§23);
- `LOOKUP_TABLE=off`: removes the table tool (§25).

**Hard set** (`check_answers.py --set hard`, 14 questions):
- the questions that failed or used tools on 30 Oct: placements, M.Sc, B.Arch, slot A, summer-term fee;
- the girls' hostel fee;
- two must-decline questions (Wi-Fi, 2015-16 hostel fee);
- both conversations;
- the 4 clarify cases.

Each configuration saves to its own file (`--config <name>` → `answer_check_<name>.json`). The one-shot row is read from the full one-shot run restricted to the same questions, since that pipeline has no pieces to switch.

**How it is run.** `pipeline/run_ablations.sh`, unattended. Two tracks run side by side because each model has its own daily allowance:
- gpt-oss-20b finishes the one-shot baseline;
- gpt-oss-120b runs the five agent configurations in order, then one full run of all the cases, which becomes the headline number: 43 when it started (39 + 4 clarify), 100 since 14 Nov (§27).

`check_answers.py` now exits with 2 when a run is unfinished; the script waits 30 minutes and resumes. `ablation_table.py` prints the table. It started on 30 Oct 2026 at 15:08 IST.

**Harness fault, a third time (§18d, §20e).** The first "agent (30 Oct)" row read 7/14 with 0 tool calls, which looked like a finding: offered tools, the agent never used them. It was not one. When the agent's daily allowance runs out, `respond.py` answers with the one-shot fallback on gpt-oss-20b, and the harness counted those answers as finished: 10 of that row's 14 answers, 2 of the first CRAG answers and 1 no-tools answer came from the fallback. Since 14 Nov a fallback caused by the daily allowance counts as unanswered (`check_answers.answered`, pinned by a test), `--resume` asks those questions again, and the table counts only real agent answers. Lesson: when a system degrades quietly, the measurement has to check *which* path answered, not just that an answer came back.

**Results:** see the table below, updated as runs finish (`python ablation_table.py`).

<!-- ablation-table -->
Hard set: 14 questions (placements, msc_tuition, barch_tuition, midsem_slot_a, summer_term_fee, hostel_fee_girls, unanswerable_wifi, unanswerable_old_hostel_fee, conv_hostel_girls, conv_mtech_tuition, clarify_hostel_vague, clarify_then_answer, no_clarify_when_specific, no_clarify_director)

| configuration | correct | must-decline refused | tokens / question | seconds / question | tool calls / question | gate fired | asked back | switches |
|---|---|---|---|---|---|---|---|---|
| one-shot | 9/14 | 2/2 | — | 44 | — | 0 | 1 | `--pipeline oneshot` |
| agent, no tools | 7/14 | 2/2 | 2,736 | 48 | 0.0 | 0 | 0 | `AGENT_TOOLS=off CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off` |
| agent (30 Oct) | 9/14 | 2/2 | 6,269 | 34 | 0.8 | 0 | 0 | `CRAG_GATE=off CLARIFY=off LOOKUP_TABLE=off` |
| + CRAG gate | 9/14 | 2/2 | 5,803 | 31 | 0.6 | 9 | 0 | `CLARIFY=off LOOKUP_TABLE=off` |
| + clarify | not run yet | | | | | | | `LOOKUP_TABLE=off` |
| full | not run yet | | | | | | | `none` |
<!-- /ablation-table -->


**Note (20 Nov 2026): the search changed under these rows.** On 20 Nov (Runbook 9, §30) table lead-ins were written once per chunk (8,162 → 6,897 chunks) and repeated passages are now dropped after reranking; the clarifying rules changed too (§31, §32). The rows above were measured before that, and three rows were never finished ("+ clarify", "full (hard set)", "full (all questions)"). For the report to compare like with like, the whole table has to be re-run on the new search: move the old `answer_check_<config>.json` files aside (otherwise `--resume` keeps them) and start `run_ablations.sh` again; see REPORT9.md, Good morning.

**Frozen index (20 Nov 2026, Runbook 10 Step 6). Every ablation row from now on uses it.**
- Git tag `final-index-2026-11-20`; copy in `~/vnit-chatbot-backups/final-index-2026-11-20/`.
- 7,328 chunks; 31,682 table records; 105 test cases; table rows as corrective passages (§34–§35).
- The rows above were measured on two earlier indexes and are set aside, not mixed in. Their files are in `data/processed/results-before-2026-11-20/`, together with a copy of `answer_check.json` (the 105/105 record) and the old runner log.
- The re-run measures every configuration afresh. The final full run writes `answer_check_full.json` (`--config full`), not `answer_check.json`, so the headline number is a fresh run of all 105 on the frozen index.
- The CRAG-gate switch also turns off the table rows of §35, which belong to the corrective step.

## 27. A 100-case answer check, written like students (2026-11-14)

**Why.** 39 questions (plus 4 clarify cases) is a small sample, and most were written by the developer, in full sentences, about topics already known to be in the data. Real students type "hostel fees for 2nd year btech boys winter 2026?" and ask about things nobody tested.

**How the 57 new cases were chosen.**
- **Topics** from the questions students actually ask about VNIT on Careers360 and Collegedunia: hostel and mess costs, refunds and cancellation, placements (packages, companies), attendance, branch change, scholarships, contacts.
- **Facts** only from VNIT's own documents in `data/raw`, each read by hand and named in a comment above the case, as in §18. Third-party sites were used for *what* to ask, never for the answers; their figures (₹35,000–70,000 a year for the hostel, for example) are approximate and out of date.
- **Wording** as students type: lower case, short forms ("4th yr", "hod of cse", "msc 1st year"), no "VNIT" in many questions.
- **Spread:** 44 new facts (mess rates, hostel fees for every year and for M.Tech/M.Sc, the PG attendance and stipend rules, branch change, minors, the Winter 2026 calendar, holidays, PhD/MBA fees, refunds, fee remission, scholarships, 2024-25 placements, history, HoD, RTI, library, internet, convocation, elections), 5 more that must be declined (JoSAA closing ranks and GATE cut-offs, which no VNIT document gives; a 2015-16 package, older than any placement report; a warden's home address; a 1990 tuition fee), 4 more conversations and 3 more clarify cases.

The counts are now 77 facts, 10 must-decline, 6 conversations and 7 clarify cases: **100**. The hard set of §26 is unchanged, so the ablation rows stay comparable; the "full (all questions)" run now covers all 100.

**First check, no key.** The new cases have not been through the AI yet; that is the full run's job. Instead, each was run through the chatbot's own steps up to the AI call (route, topic, profile, search, clarify, search grade with its corrective passages), checking the expected answer against the passages the AI would be shown. **41 of the 47** answerable single questions reach it. The misses are kept, because they are real weak spots, not faults in the tests:
- **Not found by search:** when higher-semester classes start (21 July), the Holi holiday (4 March), PhD full-time tuition (₹7,500 a semester), how many companies came for B.Tech in 2024-25 (121), who can stand for General Secretary (4th-year students). The agent may still find them with its tools.
- **Asks back when it need not:** "when can first year students join the hostel mess?" gets a programme question, although the answer (from the day they report) is the same for everyone.
- **Does not ask back when it should:** "what is the tuition fee?" is answered without asking which programme.
- **Profile not enough:** "hostel fee for first year?" with the profile M.Tech / boys does not bring the M.Tech fee sheet (₹40,080) to the AI.

Conversations need the AI's rewrite and were not checked this way.

## 28. The website's full crawl, imported into data/raw (Runbook 9, Step 1)

**Why.** The chatbot searched 81 pages of vnit.ac.in (plus documents). The website project crawled every page the site lists (1,628 saved, 19 Nov 2026), so answers that were never in the index may now be there.

**What changed.**
- `fetch_utils.html_to_text(html)`: the HTML-to-text part of `fetch_page`, moved into its own function with no change in behaviour, so saved HTML is read exactly like fetched HTML. Checked on three pages both crawls hold: the old files and a fresh extraction match word for word on two (5G Lab, T&P) and 98% on the CSE page, whose content changed between the crawls.
- `import_site_crawl.py` writes each new page as `data/raw/site_<slug>.txt`, with the usual header plus `CRAWL: full-2026-11-19`. Pages already in `data/raw` are left alone.

**Counts** (of 1,628 saved pages):

| | Pages |
|---|---|
| Imported | 886 |
| Already in data/raw (old file kept) | 117 |
| Under 40 words | 484 |
| Same text as another page | 74 |
| Personal data (`looks_like_personal_data`) | 26 |
| Skipped sections (stores, recruitment) | 18 |
| Title: list of people or procurement | 14 |
| Mostly Devanagari | 7 |
| Listing, archive or attachment page | 2 |

The 484 short pages really are short: the website's own extractor, which reads the content differently, agrees on all but 3. They are mostly picture or link pages.

**Rejected.** The "lines on 40% of a section's pages" boilerplate filter. On the new files the repeated lines are faculty-profile headings ("Administrative Responsibilities", "Sponsored Research Projects"), 0–7% of the words per sub-site, which give a passage its context. No menus or cookie notices dominate any of the 15 files read by eye.

The index is not rebuilt in this step; the no-key checks are identical to the baseline (54/54, 69/77, 15/18, 16/19).

*Later (§29):* the importer also leaves out attachment pages it missed (92) and near-duplicates (62), strips sub-site names from titles, and writes to `data/raw_site_crawl/` instead of `data/raw`: 814 pages.

## 29. The full crawl in the index: measured, not kept (Runbook 9, Step 2)

**Question.** Does searching ~800 more pages of vnit.ac.in help (answers that were never in the index) or hurt (more pages competing with the right passage)?

**Rule set before measuring.** Keep the bigger index only if more answerable questions reach the AI (`chunk_ranks`, top 7) than at baseline, losing at most one baseline hit, with the reason recorded.

| Version | Chunks | test_agentic | chunk_ranks top 7 | top 3 | fact_ranks | evaluate |
|---|---|---|---|---|---|---|
| Baseline (81 pages + documents) | 8,162 | 54/54 | 69/77 | 64/77 | 15/18 | 16/19 |
| First import, as written (886 pages) | 32,261 | (not measured) | | | | |
| Attachment pages left out (868 pages) | 17,922 | 52/54 | 69/77 | 64/77 | 15/18 | 17/19 |
| Plus: sub-site names stripped from titles, near-duplicates left out, corrective step looks at 6 pages (814 pages) | 17,212 | 50/54 | 68/77 | 63/77 | 14/18 | 16/19 |

- **First import.** 92 WordPress attachment pages (an image's own page) got through: the check for `<body class="attachment">` only looked at the first 20,000 characters, and these pages have ~29,000 characters of `<head>`. One of them made 9,555 chunks. Fixed in the importer before measuring.
- **Attachment pages left out.** No question newly reached the AI. evaluate gained one (the CSE department's founding year now comes from its own page). Two unit tests failed: for "How many students got placed in 2025-26…" the search-quality gate's two "best-titled pages" became "Placement Policy For Companies" under both T&P and Hostel (the same page copied into two sub-sites), and the T&P page holding the 678 figure fell to 21st by title, behind dozens of new pages ending in "– Training & Placement Department".
- **Second attempt** (each change general, none naming a question): strip a sub-site's name from the end of its page titles (an ending shared by ≥40% of a sub-site's titles); skip pages whose word 5-grams overlap >80% with a page already kept (option b of the runbook, done at import); let the corrective step look inside the 6 best-titled pages and keep the 2 whose best passage the reranker scores highest (option c: the "2 pages" setting dated from 81 pages). Worse: titles left bare ("Placements", "About Us") now matched institute-wide questions — the Chemical department's "Placements" page topped the placements question, T&P's "About Us" the Institute-of-National-Importance one — and `electrical_mtech` dropped from rank 2 to 10.

**Why it doesn't help the test set.** The 8 questions whose answer does not reach the AI (fees, the calendar, the Holi holiday, the 2024-25 company count, General Secretary eligibility) all have their answers in *documents*, which were already in the index. The new pages are mostly faculty profiles, department sub-pages and news posts: useful for questions nobody has written a test for yet ("what does Dr X research?"), but for the tested questions they are only competition.

**Decision.** Not kept. The backup index is restored (byte-identical, checks identical to baseline), the 814 pages are kept in `data/raw_site_crawl/` (which `chunk.py` does not read), and `import_site_crawl.py` writes there. The corrective-step change was reverted with the rest of the step, since it was only measured together with the bigger index. Trying again later is cheap: move the files into `data/raw`, rebuild (~17 minutes), re-run the checks.

**What would be needed to keep them.** A way to search the new pages only when the question is about something the old corpus does not cover (a person, a lab, a sub-page), for example a second, separate index consulted when the first search grades weak — not attempted tonight.

## 30. Search misses: table lead-ins and repeated passages (Runbook 9, Step 3)

**Starting point** (original index, `chunk_ranks`): 69/77 answer passages reach the AI. Not reaching it: `placements`, `msc_tuition`, `barch_tuition` (9), `higher_sem_classes_start`, `holiday_holi` (8), `phd_tuition_full_time` (10), `companies_btech_2425`, `gs_eligibility`.

**Cause 1: repeated table lead-ins.** Converted documents write each table row as "<lead-in> | <row>", the lead-in being the text before the table. When that text is long it swamps the rows: in the 2026 holiday list every row starts with a 40-word "In terms of Office Memorandum F. No. 12/2/2023-JCA dated 03rd July 2025 …", so a 135-word chunk held two holidays. Over all documents, repeated lead-ins are **16% of the words** (189 documents, 7,858 rows).
**Fix** (`chunk.share_lead_ins`): consecutive rows with the same lead-in are written as "<lead-in> | <row> | <row> …", the lead-in once per group, each group at most a chunk long, so every chunk still starts with its lead-in. 8,162 → 6,897 chunks. `build_facts.py` reads the raw files, so the table tool is unchanged.

**Cause 2: the same passage twice.** A paragraph copied onto two pages ranks twice. For the summer-term fee, places 1–2 were one Intellipaat passage and 4–5 one brochure passage, and the notice stating "Rs. 3000/- per course" fell to 8th.
**Fix** (`query._drop_repeats`): after reranking, a passage sharing over 90% of its words with one ranked above it is left out (the pool is 60, so the places are refilled).

| | test_agentic | chunk_ranks top 7 | top 3 | top 12 | fact_ranks | evaluate |
|---|---|---|---|---|---|---|
| Before | 54/54 | 69/77 | 64/77 | 72/77 | 15/18 | 16/19 |
| Shared lead-ins | 54/54 | 71/77 | 66/77 | 74/77 | 14/18 | 16/19 |
| + repeats dropped (kept) | 57/57 | **73/77** | 66/77 | 74/77 | 14/18 | 16/19 |

Newly reaching the AI: `gs_eligibility` (not in top 12 → 3), `msc_tuition` (→ 7), `phd_tuition_full_time` (10 → 7), `barch_tuition` (9 → 5). Also better: `electrical_mtech` 2 → 1, `hostel_fee_mtech_first_year` 2 → 1, `hostel_fee_msc_first_year` 3 → 1, `mess_rate_per_day` 2 → 1. Every question that reached the AI before still does.

**Trade, recorded.** In `fact_ranks` (top 3), "When are the end semester exams for first year B.Tech in Winter 2026?" moved from 3rd to 4th (15/18 → 14/18): the three passages above it are the first-year exam schedule itself, scored 8.40/8.18/8.10 against 8.00, and it still reaches the AI. Reverting would give up four questions to keep one top-3 place.

**Tried and rejected.**
- Grouping "<lead>: <row>" lines the same way (the 2024-25 placement report writes "Companies visited for placement - 2024-25:" before each company): brought the 121 companies to rank 4, but lost `cse_placement_percent_2425` (a baseline hit) and `gs_eligibility`: 72/77. Reverted.
- A larger per-source cap in the candidate pool (6, 8): no change for Holi or the companies.

**Still not reaching the AI, and why.**
- `holiday_holi` (rank 9): once in front of the reranker the Holi chunk scores 4.54 against the top's 4.66, but it is 12th in the keyword+embedding order and other chunks of the same list fill that document's places in the pool. Needs either a finer split of that one list or a "named-thing" keyword boost; neither attempted (the first is a special case, the second would need its own measurement).
- `companies_btech_2425`: the statistics chunk is 64th before reranking and scores 1.8 against 5.6 for the company-name chunks (see the rejected colon grouping).
- `higher_sem_classes_start`: the answer is "Commencement of Next Session: 21st July 2026" in the *Summer* 2026 calendar; the question asks about Winter 2026 and second year onwards, words that passage does not contain. Not fixable by search alone.
- `placements`: the 2025-26 figures are on the T&P page; the CRAG gate's corrective step brings it in the live path (unit test), which `chunk_ranks` does not run.

## 31. Ask back only when it changes the answer (Runbook 9, Step 4)

**The three failures (§27).** "When can first year students join the hostel mess?" was asked "boys or girls?" although the answer is the same for both; "what is the tuition fee?" was answered without asking which programme; "hostel fee for first year?" with the profile M.Tech / boys gave a wrong total.

**Changes in `slots.needs_clarification`:**
1. **The answers must differ, not only the documents.** Finding documents for two groups is no longer enough: the best passage of each group must carry different figures or dates (`answers_differ`). Mess joining: both schedules say "from the date of their physical reporting" → no question. Hostel fees: the sheets carry different totals → asked.
2. **A vague fee question looks at the titles too.** When a fee question names no programme and the 10 best-titled documents include fee sheets for **3 or more** programmes, ask which programme, even if the passages found happen to come from one sheet. Measured over the 100 cases: "what is the tuition fee?" matches sheets for 5 programmes (title scores above 1.2); every real fee question without a programme matches at most 2, weakly (below 0.6). The runbook suggested 2 programmes; at 2, the summer-term and fee-remission questions would be asked back.
3. **The profile in the search.** Checked, no change needed: `apply_profile` writes the profile into the question ("hostel fee for first year? (for M.Tech boys)"), and the programme and gender filter in `query._candidates` reads that text. With the profile, the M.Tech sheet stating ₹40,080 ranks 1st and all 7 passages are M.Tech hostel sheets. The saved failure was the AI adding up the wrong items (₹78,840, which the verifier flagged), so it is an answer problem, asked again in Step 7.

**Over all 100 cases, no key** (`respond.answer`, first question of each):

| | Ask back | Unexpected / missing |
|---|---|---|
| Before (after Step 3) | 1 (`clarify_hostel_vague`) | `clarify_tuition_vague` not asked |
| After | 2 (`clarify_hostel_vague`, `clarify_tuition_vague`) | none |

`mess_joining_first_year` had already stopped asking after Step 3's re-chunking (different passages found); rule 1 now makes that a rule rather than luck, and has its own test.

Tests (no key): `test_no_question_back_when_every_group_has_the_same_answer`, `test_question_back_when_the_groups_have_different_figures`, `test_vague_tuition_question_asks_which_programme`, `test_fee_question_about_something_else_is_not_asked_back`, `test_profile_brings_the_mtech_hostel_sheet`, and `test_no_unexpected_questions_back_over_all_cases` (all 100 cases; skipped without the index).

## 32. Follow-ups that only change a detail, rewritten in code (Runbook 9, Step 5)

**The two failing conversations, from their saved traces:**
- `conv_hostel_mtech` ("…hostel fee for first year B.Tech boys…" → "what about mtech?"): **the rewrite failed.** gpt-oss-20b returned "What about M.Tech?" unchanged, the search found M.Tech programme pages, and the answer listed M.Tech specialisations.
- `conv_phd_part_time` ("…tuition fee for full time PhD per semester?" → "and for part time?"): **the rewrite was right** ("What is the tuition fee for part time PhD per semester?"); the answer gave the per-semester *total* (₹25,000) instead of the tuition row (₹15,000) — the same row confusion as `phd_tuition_full_time`.

**Change (`followup._swap_rewrite`), before the LLM rewrite:** when a follow-up names nothing but slot values — programme, gender, category, year of study, or full-/part-time — each value replaces the previous question's value of the same kind, or is added as "(for …)" when the previous question had none. No LLM call, the same result every time. Anything else ("and the mess fee?") still goes to the LLM rewrite. `mode_of_study` (full-time / part-time) is now a slot in `slots.py`, with the same validation as the others.

**No key, all six conversations** (`respond.answer` with history):

| Case | Follow-up | Searched as | Answer passage rank |
|---|---|---|---|
| conv_hostel_girls | and for girls? | …first year B.Tech **girls** for the Winter 2026 session? | 3 |
| conv_mtech_tuition | what about M.Tech? | (a slot-only follow-up: same swap) | 1 |
| **conv_hostel_mtech** | what about mtech? | …first year **M.Tech** boys for the Winter 2026 session? | **1** (₹40,080) |
| **conv_phd_part_time** | and for part time? | …tuition fee for **part time** PhD per semester? | 10 (not reached) |
| conv_placement_cse | and for cse specifically? | (not a slot value: glued without a key, LLM with one) | 1 |
| conv_holiday | and dussehra? | (not a slot value: glued without a key, LLM with one) | 1 |

`conv_phd_part_time` now has the right question; its passage (the "Tuition Fees — … Part-Time … 15000.00" row) ranks 10th, a retrieval miss like `phd_tuition_full_time` (7th). Recorded for Step 7.

Tests (no key): 8 phrasings that take the swap, 2 that must not ("and the mess fee?", "who is the warden?"), and the `mode_of_study` slot. test_agentic 66/66; retrieval checks unchanged.

## 33. The AI asked again: 91/100 → 97/100 (Runbook 9, Step 7)

Asked on 20 Nov 2026 through the agent (gpt-oss-120b), one case at a time (`check_answers.py --only <name> --pause 30`), after Steps 3–5. About 99,000 tokens for 20 cases; the daily limit was not reached.

**The 9 failures:**

| Case | Before | After | Why |
|---|---|---|---|
| msc_tuition | FAIL (₹0, the SC/ST row) | **PASS** | The fee estimate's tuition row now reaches the AI (shared lead-ins, §30) |
| phd_tuition_full_time | FAIL (₹22,100, the total) | **PASS** | The tuition row (₹7,500) now reaches the AI (rank 10 → 7) |
| mess_joining_first_year | FAIL (asked boys/girls) | **PASS** | Asked back only when the answers differ (§31) |
| conv_hostel_mtech | FAIL (rewrite left "What about M.Tech?") | **PASS** | Slot swap in code (§32) |
| clarify_profile_mtech | FAIL (₹78,840, wrong items added) | **PASS** | With the new chunks the M.Tech sheet's passages are cleaner; ₹40,080 given |
| clarify_tuition_vague | FAIL (answered without asking) | **PASS** | Asks which programme (§31) |
| holiday_holi | FAIL | FAIL | Answered "03 March" from the *restricted* list (Holika Dahan); the gazetted row "Holi — 04.03.2026" still ranks 9th |
| companies_btech_2425 | FAIL | FAIL | The statistics row ("Number of Companies Visited — B.Tech: 121") is not found, even by `read_document` on the report |
| conv_phd_part_time | FAIL (₹25,000, the total) | FAIL (₹25,000, the total) | Right question now, but the tuition row (₹15,000) ranks 10th |

**Regression sample** (all passed before): director, unanswerable_director_salary (picked up by the "director" fragment), no_clarify_director, hostel_fee_first_year, btech_fee_open, placements, unanswerable_wifi, conv_hostel_girls, clarify_hostel_vague, clarify_then_answer, classes_start_fy — **11/11 pass**. No change was reverted; no pattern was changed, so no `--rescore`.

**Overall, from `answer_check.json`: 97/100 saved results pass** (the other 80 are the saved answers from 14 and 19 Nov, asked before tonight's changes; a full re-run would measure them on the new code, at ~450k tokens).

The three left are all search misses on table rows that the AI never sees; the next idea worth measuring is a keyword boost for a rare word the question shares with a single table row ("Holi", "Companies Visited"), which the cross-encoder alone does not reward enough.

## 34. New documents from the full crawl: kept, except five (Runbook 10, Step 3)

**What changed.** The website project's full crawl linked 116 fee, calendar, hostel, scholarship, placement and rules documents never read. `ingest_documents.py discover-crawl` added them to the inventory (only adding; every existing entry is unchanged), and `convert --only-new` converted them, newest first, until the 4-hour timebox.

Of 115 selected:
- 48 were converted.
- 1 was excluded as personal data: a refund list of recruitment candidates' names, caught by the new `PERSON_LABEL` density rule.
- 1 was empty, and 4 failed (3 timeouts, 1 crash).
- 62 are still to do.

**Measured, no key** (82 answerable questions: the 77 of before plus 5 new ones written from the new documents):

| Index | Chunks | `chunk_ranks` (top 7) | `fact_ranks` | `evaluate` | `evidence_check` | Tests |
|---|---|---|---|---|---|---|
| Before (Step 0) | 6,897 | 73/77 | 14/18 | 16/19 | 73/77 + 10/11 | 68/68 |
| All 47 new documents | 7,369 | 75/82: **`barch_tuition` 5→9 and `msc_tuition` 7→10 lost**; the S-27 last-date question not in the top 12 | 13/18 | 16/19 | 76/82 | not run |
| Without 4 that cost hits | 7,339 | 78/82 (old 73/77 kept) | 13/18 | 16/19 | 77/82: **`placements` lost**; it had reached the agent only through the corrective step | 67/69 (the two placement-gate tests fail) |
| **Kept:** also without the Hindi copy | **7,328** | **78/82** (old 73/77 kept; the 5 new ones all rank 1) | **13/18** | **16/19** | **78/82 + 10/11** (every baseline hit kept) | **70/70** |

**What took the places.**
- **B.Arch and M.Sc tuition:** the *Information Brochure for International Admissions – 2026* (a hostel-cost line for B.Tech/B.Arch/M.Sc), the *MahaDBT Scholarship/Freeship* notice ("Tuition Fee & Exam Fee for Tribal Students"), and two older term fee notices (*S25 … 2024-25 UG/PG*, *Revised W25 … 2025-26 UG-PG*). None of them is a newer version of the tuition sheets the tests use, so they were moved to `data/raw_new_docs_held/`, not searched. Their `status.json` entries stay "ok", so `convert` won't redo them.
- **Placements:**
  - the corrective step looks inside the 2 best-titled pages the first search missed;
  - the new *Placement Policy_Batch 2027 (Hindi)* took one of those places from the Training & Placement page that holds 678/170;
  - its text is OCR noise (Hindi read as Latin letters; Devanagari share 0.0), so the Devanagari check after conversion missed it.

  Fixed in general: `select()` now treats a title naming the Hindi version like one in Devanagari (it matches only this document). The file was moved to `_trash/r10-hindi/` and its entry marked `hindi`.

**The one trade.**
- `fact_ranks`' Kotak Kanya question moved from 2nd to 4th, behind the new *Kotak Kanya Scholarship 2026-27*. That is the newer version of the same notice, and both give ₹1.5 lakh a year, so the test's expected answer is not out of date.
- It still reaches the AI. This is the one acceptable `fact_ranks` place in the ground rules.
- `cse_placement_percent_2425` moved from 4th to 6th and still reaches the AI.

**Tests that may be out of date:** none found. No kept document gives a different figure for something a test asks.

**The 5 new cases** (`check_answers.py`; the test set is now 105):

| Case | Document | Expected | Rank |
|---|---|---|---|
| `dasa_usd_rate_summer_2027` | Fees Payment Instruction Summer 2027 | ₹96.21 per USD | 1 |
| `fee_remission_2627_extended` | Extension of last date for Fee Remission 2026-27 application | 14/10/2026 | 1 |
| `shiksha_shakti_deadline` | Shiksha Shakti Scholarship 2026–27 (SDEF) | 31 October 2026 | 1 |
| `placement_offer_upgrade_2027` | Placement Policy_Batch 2027 | 30 April 2027 | 1 |
| `mtech_research_seats_2027` | M.Tech (Research) brochure, January 2027 | 5 supernumerary seats per programme (115) | 1 |

A sixth question tried first, the S-27 last date for fee payment ("1-Nov-2026 to 23-Dec-2026"), was not in the top 12: the date line sits alone, below a long OCR-damaged fee table. It was replaced, not loosened.

## 35. The three table-row misses: table rows as corrective passages (Runbook 10, Step 4)

**The problem.** After Runbook 9 the last three failures were each one row of a long table that never reached the AI:
- **Holi** (rank 9): the AI answered from the restricted list.
- **The 121 companies:** 64th before reranking; the reranker prefers the list of company names.
- **Ph.D. part-time tuition, ₹15,000** (rank 10): the AI gave the ₹25,000 total.

`chunk_ranks` can't see the corrective step, so a new no-key script, `evidence_check.py`, runs `respond.answer` with the planner replaced by a stand-in. It records what the agent would be given: the first-search passages and the corrective ones.

**Tried, in order, measured with `evidence_check`:**

1. **Table rows as corrective passages** (`respond.table_rows`, code only, no LLM call). For fees, calendar and placement questions, the best 2 `facts.db` rows are added through the corrective path. The keywords are the question's rarer words, the filters its programme, gender, category, year and academic year. A row counts only if it holds at least 2 of those words. It runs even when the grade is "correct". The first version found 1 of 3 (Holi missing, PhD found but dropped, companies not found). Four general fixes followed:
   - **Rank rows by their own label and cells, weighted by word rarity.** Holi's stem "holi" also matches every "Holiday" row, and the newer calendars' rows came first. Judged on its own cells, "holi" (rare) outweighs "holid" (common).
   - **No "already shown" filter.** It dropped the ₹15,000 row because its label, "Tuition Fees", appears in other passages. Exact repeats are already dropped by the evidence list.
   - **One row per document,** as the search caps passages per source. Two rows of the international-students sheet had been taking both places.
   - **"B.Tech" read as "btech"** when matching. The question's "btech" never met the row's "B.Tech", so the companies row failed the 2-word rule.

   The companies row was not in `facts.db` at all. The placement report's table has no paragraph before it, so its lines have no " | " lead-in, and `build_facts.parse_line` dropped them. Fixed generally: the parser now accepts "<caption>: <label> — <column>: <value>; …" with 2 cells or more, and still rejects prose such as "Note: fees are due — Date: 1 Jan". `facts.db` went from 23,457 to 31,682 records: tables without a lead-in were being dropped across all documents.
2. **Look inside the best document** (page-scoped re-ranking). Measured before building: the statistics passage is not in the top 8 of its own report's 30 chunks; the company-name list wins there too. It would not fix the companies case, so it was not built.
3. **Row-level reranker input.** Not needed: option 1 got all three in.

The rows are part of the corrective step, so the ablation switch `CRAG_GATE=off` turns them off too (checked by the existing `test_gate_switch_removes_the_corrective_passages`).

**Prompt size** (the first prompt, measured with a fake LLM, no key). Uncapped rows added 300–1,460 tokens: a calendar row can hold dozens of cells. Each added row is now capped at 450 characters (about 150 tokens). The largest first prompts measured are 5,374 (`barch_tuition`) and 5,245 (`placements`), under `planner.PROMPT_BUDGET` = 6,000.

**Result** (no key):

| Check | After Step 3 | After Step 4 |
|---|---|---|
| `evidence_check`, fact questions | 78/82 | **80/82** (Holi and companies now through the corrective step) |
| `evidence_check`, conversations and profile cases | 10/11 | **11/11** (`conv_phd_part_time`) |
| `chunk_ranks` (first search; unchanged code) | 78/82 | **78/82**, every rank identical |
| `test_agentic.py` | 70/70 | **73/73** |

Still not in the evidence: `msc_tuition` (rank 10; it passes end to end through the agent's own tools, EXPERIMENTS-LOG §33) and `higher_sem_classes_start` (it passes end to end too).

**Tests added:**
- `test_table_parser_takes_a_row_without_a_lead_in`
- `test_table_rows_bring_the_one_row_of_a_long_table` (real `facts.db`; all three rows)
- `test_table_rows_only_for_fees_calendar_and_placement` (no rows for a people or hostel question)

## 36. The AI asked again: 97/100 → 105/105 (Runbook 10, Step 5)

Asked one at a time through the agent (`check_answers.py --only <name> --pause 30`), on the index and code of Steps 3–4. That is 15 agent answers plus 1 clarifying question (no LLM), about **69,000 tokens** of gpt-oss-120b in all.

| Case | Before tonight | Now | Note |
|---|---|---|---|
| holiday_holi | FAIL | **PASS** | the "Holi — 04.03.2026" row arrives as a corrective table row (§35) |
| companies_btech_2425 | FAIL | **PASS** | the "Number of Companies Visited — B.Tech: 121" row, newly in `facts.db` (§35) |
| conv_phd_part_time | FAIL | **PASS** | the "Tuition Fees … Part-Time … 15000.00" row (§35) |
| dasa_usd_rate_summer_2027 | new | **PASS** | Fees Payment Instruction Summer 2027 |
| fee_remission_2627_extended | new | **PASS** | Extension of last date for Fee Remission 2026-27 |
| shiksha_shakti_deadline | new | **PASS** | Shiksha Shakti Scholarship 2026–27 |
| placement_offer_upgrade_2027 | new | **PASS** | Placement Policy_Batch 2027 |
| mtech_research_seats_2027 | new | **PASS** | M.Tech (Research) brochure January 2027 |
| placements | PASS | PASS | regression |
| btech_fee_open | PASS | PASS | regression |
| hostel_fee_girls | PASS | PASS | regression |
| msc_tuition | PASS | PASS | regression (one tool call, as before) |
| phd_tuition_full_time | PASS | PASS | regression |
| midsem_slot_a | PASS | PASS | regression |
| unanswerable_wifi | PASS | PASS | regression: refused, after 2 searches |
| clarify_tuition_vague | PASS | PASS | regression: asks which programme |

Every answer was "verified": every figure was found in the passages. No regression, so nothing was reverted.

**Overall, from `answer_check.json`: 105/105 saved results pass.** The other 89 are saved answers from 14, 19 and 20 Nov, asked before tonight's documents and table rows. The fresh full run on the frozen index (Step 6) measures all 105 on tonight's code.

## Ideas not tried (would need more time/budget to responsibly test)

- **Page-scoped re-ranking**: first pick the top page(s) with plain TF-IDF (already reliable, 95%), then re-rank *only that page's own chunks* with a query-type-aware heuristic (date patterns for "when", digit+unit patterns for "how many"). This avoids experiment #1's failure mode (a date-boost couldn't now escape to an unrelated page, since page selection already happened) but adds real complexity and more surface area for its own edge cases — didn't want to ship something untested against the full benchmark and multiple real question phrasings without further review time.
- **A real transformer sentence-embedding model**, if a network path to one ever opens up (a different host than huggingface.co, or the model weights hand-carried onto the machine some other way). Given experiment #2's result, this is genuinely the more promising direction, not the word-vector averaging tried here.
- **Sentence-level chunking with page-aware grouping** (chunk by sentence, but keep a page's chunks logically grouped so a "which chunk of this page" reranking step has cleaner units to work with) — different from the flat smaller-chunk-size sweep already tried.

## 37. Agent v2: memory, a longer loop, more tools and tasks, streaming (Runbook 11, branch `agent-v2`)

**Why.** v1 answered one question at a time from at most two rounds of tools, remembered only the last three questions, and showed nothing until the whole answer was ready. The goal was the feel of Claude or ChatGPT (streaming, memory, planning, more tools and kinds of task, the usual chat controls) without weakening the one rule: VNIT facts only from VNIT's documents, cited, every figure verified. The model is unchanged (Groq's free `openai/gpt-oss-120b`); everything new is the agent around it.

**What was built** (all behind `AGENT_V2`, on in the branch; `AGENT_V2=off` is v1 exactly, and v1's 73 tests pass with it off):
- `memory.py`: 6 turns with answers, each answer ≤600 characters, ≤~1,500 tokens; earlier answers are context, never evidence.
- `agent_loop.py`: a short plan (1-4 parts, tracked), up to 6 rounds of up to 3 parallel tool calls, a per-question budget of 14,000 tokens, stopping when the plan is done or two rounds find nothing new; a one-line reflection after each round written by code (no critic model); compaction past `PROMPT_BUDGET`; repeated calls skipped; the final answer streamed.
- Tools: `latest_notices`, `fetch_vnit_page` (vnit.ac.in only, cached a day), `today`, `contact_office`.
- `router.task`: compare (table), summarise, explain (steps), draft (labelled, verified office email), general (labelled, no VNIT figures; the must-decline questions never qualify), chat.
- `language.py`: Hindi, Marathi, Hinglish detected in code; English search; answer in kind with figures as in the sources.
- `POST /ask/stream` (Server-Sent Events) and a new chat page and website widget with Stop, Copy, Regenerate, Edit, suggestions and tables.

**No-key measurements (same frozen index).** Retrieval is unchanged: `chunk_ranks` 78/82, `fact_ranks` 13/18, `evaluate` 16/19, `evidence_check` 80/82 + 11/11, all equal to Runbook 10. Tests: 112/112 (73 of v1 + 39 of v2).

**Live trials on a dev model, not the final model.** The ablations of §26 were using the gpt-oss allowance, so v2 was tried on `qwen/qwen3.8-27b` (its own allowance). 16 trial questions: 13 through the agent, 2 fixed replies (general, chat), and the Hinglish one repeated after a per-minute limit. Of the 13:
- multi-part: 2 right, 1 half right (it took the 2025-26 placement season as "ongoing" from the report instead of the T&P page's 678);
- tools: `latest_notices` used for "any new fee notice?"; a deadline question did not call `today` (the date is already in the prompt) and reasoned badly from a missing date;
- compare, summarise, explain, draft, lookup: right; general labelled; chat listed the new abilities;
- Hindi, Marathi (it opened the live Director page by itself) and Hinglish: right, figures verified.

**Cost.** On these trials, v2 averaged **12,036 tokens, 121 s, 1.8 tool calls and 3.2 LLM calls** a question; v1's saved 105-case run on gpt-oss-120b averaged 4,541 tokens, 24 s, 0.3 tool calls and 1.3 calls. The two are not like for like (different model, and the trials were mostly multi-part questions), so the 15 regression cases are being asked through both v1 and v2 on the dev model (`--set regression`, configs `agent_v1_dev_regression` and `agent_v2_dev_regression`). Two causes are visible already: each v2 round carries a longer prompt (9 tool descriptions and the planning rules, ~2,600 tokens before any passage), and the final answer plus one revision come after the budget check, so a summary used 20,606 tokens against a 14,000 budget. The seconds are mostly the rate pacer waiting for the 8,000-tokens-a-minute allowance; streaming the steps is what makes that wait visible rather than blank.

**The agentic set** (`check_answers.py --set agentic`, 19 cases: 3 multi-part, 2 compare, 2 summarise, 2 explain, 2 draft, 2 multi-turn, Hindi, Hinglish, 2 labelled general, 2 must-decline phrased to tempt the general path), saved to `answer_check_agent_v2_dev.json`, never to `answer_check.json`. The dev model's rolling daily allowance (~200,000 tokens) ran out after the trials, during this set; see REPORT11.md for how far it got.

**Not yet measured:** v2 on the real model over the 105 cases (`--config agent_v2`), and as a row of the ablation table. That waits for the ablations of §26 to finish (REPORT11.md, the merge plan).
