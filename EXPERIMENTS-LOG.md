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

Experiments 10–16 were measured with 185 documents indexed. Re-measured after converting everything VNIT links — 81 pages + 406 documents, 8,147 chunks, 2.2× the chunks of the §12–16 runs:

| Check | 148 docs (09-22) | 185 docs (10-02) | **406 docs (10-03)** |
|---|---|---|---|
| `check_answers.py` | 13/18 | 17/18 | **17/18** |
| `fact_ranks.py` | 12/18 | 15/18 | 14/18 |
| `evaluate.py` | 16/19 | 16/19 | **17/19** |

Worth noting honestly: end-to-end answers held at 17/18 and page-level rose, while the answer-chunk measure slipped by one — tripling the corpus adds competition, and two facts moved from rank 3 to rank 4 (end-semester exams, which the LLM still answers correctly, because `generate.py` sends up to 5 passages per sub-question). That gap between "chunk ranked in the top 3" and "answer is correct" is the reason all three checks are kept rather than one.

Also re-ran during this round: the personal-data filter over all 406 converted documents, with nothing flagged. That check matters because a run killed between writing a document's text and saving `status.json` leaves a text file whose result was never recorded (14 such files); the filter runs before the write, so they were already screened, and this confirmed it.

## Ideas not tried (would need more time/budget to responsibly test)

- **Page-scoped re-ranking**: first pick the top page(s) with plain TF-IDF (already reliable, 95%), then re-rank *only that page's own chunks* with a query-type-aware heuristic (date patterns for "when", digit+unit patterns for "how many"). This avoids experiment #1's failure mode (a date-boost couldn't now escape to an unrelated page, since page selection already happened) but adds real complexity and more surface area for its own edge cases — didn't want to ship something untested against the full benchmark and multiple real question phrasings without further review time.
- **A real transformer sentence-embedding model**, if a network path to one ever opens up (a different host than huggingface.co, or the model weights hand-carried onto the machine some other way). Given experiment #2's result, this is genuinely the more promising direction, not the word-vector averaging tried here.
- **Sentence-level chunking with page-aware grouping** (chunk by sentence, but keep a page's chunks logically grouped so a "which chunk of this page" reranking step has cleaner units to work with) — different from the flat smaller-chunk-size sweep already tried.
