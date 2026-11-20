# Runbook 10 progress

Read this first after a restart; carry on from the first step not marked DONE, FAILED or SKIPPED.

| Step | Status | Note |
|---|---|---|
| 0 | DONE | tag `before-runbook-10`, backups, baseline 68/68, 73/77, 14/18, 16/19 |
| 1 | DONE | `discover-crawl` added 116 documents (115 selected, tier 0); existing entries unchanged |
| 2 | DONE | timeboxed at 4 h: 47 kept, 1 excluded (list of candidates), 1 empty, 4 failed, 62 still to do |
| 3 | DONE | kept 42 new documents; 4 held (cost B.Arch/M.Sc tuition), Hindi copy excluded (cost placements); 78/82, 13/18 (Kotak trade), 16/19, 70/70; 105 cases (§34) |
| 4 | DONE | table rows as corrective passages + parser takes rows without a lead-in: all 3 in the evidence; evidence 80/82 + 11/11, chunk_ranks 78/82, tests 73/73 (§35) |
| 5 | DONE | 16/16 pass (3 misses fixed, 5 new, 8 regression); saved results 105/105; ~69k tokens (§36) |
| 6 | DONE | tag `final-index-2026-11-20`, frozen copy, old results in data/processed/results-before-2026-11-20/, runner started 18:28 |
| 7 | DONE | README, APPLICATION, HOW-TO-RUN, website check on 8010, Good morning |

## Decisions

- Step 0: the runbook file itself was untracked; it is committed with Step 0.
- Step 1: the two new tests were written before Step 0's test run started, so the baseline test count is 68/68 (66 old + 2 new).
- Step 1: `count_new_documents.py` now calls the shared `crawl_links`/`crawl_candidates`, so its 116 and `discover-crawl`'s 116 are the same list by construction. People/procurement count 45 (was 44): link text kept to 200 characters, as `discover()` does.
- Step 1: `--only-new` reads every `data/documents/added_*.json`, not one dated file, so a later run on another day still finds them.
- Step 2: no old failures would be retried (every old selected document is in status.json), but `--only-new` was used anyway.
- Step 2: timebox hit with 62 of 115 not converted; the run moves on with the 47 kept, as the runbook says. The order was newest-first in tier 0, so the most recent fee/calendar notices are among those converted.
- Step 2: a converted recruitment-candidates refund list passed the old privacy rules; added the PERSON_LABEL density rule (flags only that document of all 454) rather than a title rule, since its title says "candidates" only as "in respect of candidates".
- Step 3: the S-27 last-date question (first choice of the 5) didn't rank, so it was replaced by the M.Tech (Research) seats question instead of loosening anything.
- Step 3: `evidence_check.py` (written early, for Step 4) was used here too, because `chunk_ranks` can't see the corrective step: it caught the placements loss that `chunk_ranks` would have missed.
- Step 3: the held documents keep `status.json` "ok"; their files are in `data/raw_new_docs_held/`, so a re-run of convert won't redo them and moving them back is one rebuild.
- Step 3: the one fact_ranks trade (Kotak Kanya 2 -> 4) is the newer version of the same notice with the same figure; kept.
- Step 4: the table rows run inside the corrective gate block, so CRAG_GATE=off removes them as well (ablation consistency), and they are added even when the grade is "correct", as the runbook says.
- Step 4: option 2 was measured (retrieve_within on the placement report) before building and could not fix the companies case, so it was not built; option 3 was not needed.
- Step 4: `facts.db` is rebuilt (31,682 records), the passage index is the Step 3 one (7,328 chunks). The Step 3 facts.db is kept in `../_trash/facts_step3.db`.
- Step 4: rows capped at 450 characters after measuring that uncapped calendar rows added up to ~1,460 tokens to the first prompt.
- Step 6: the old runner log was moved aside with the old results (not deleted), so the new log starts clean; the final full run already writes `answer_check_full.json`, so `run_ablations.sh` was not edited.
- Step 6: about 170k gpt-oss-120b tokens were spent today (Runbook 9 ~99k + Step 5 ~69k), so the agent track will reach the daily limit quickly tonight and carry on tomorrow by itself (it retries every 30 minutes).
