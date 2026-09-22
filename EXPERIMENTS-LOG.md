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

## Ideas not tried (would need more time/budget to responsibly test)

- **Page-scoped re-ranking**: first pick the top page(s) with plain TF-IDF (already reliable, 95%), then re-rank *only that page's own chunks* with a query-type-aware heuristic (date patterns for "when", digit+unit patterns for "how many"). This avoids experiment #1's failure mode (a date-boost couldn't now escape to an unrelated page, since page selection already happened) but adds real complexity and more surface area for its own edge cases — didn't want to ship something untested against the full benchmark and multiple real question phrasings without further review time.
- **A real transformer sentence-embedding model**, if a network path to one ever opens up (a different host than huggingface.co, or the model weights hand-carried onto the machine some other way). Given experiment #2's result, this is genuinely the more promising direction, not the word-vector averaging tried here.
- **Sentence-level chunking with page-aware grouping** (chunk by sentence, but keep a page's chunks logically grouped so a "which chunk of this page" reranking step has cleaner units to work with) — different from the flat smaller-chunk-size sweep already tried.
