# Runbook 9 progress

Read this first after a restart; carry on from the first step not marked DONE or FAILED.

| Step | Status | Note |
|---|---|---|
| 0 | DONE | tag `before-runbook-9`, backups in `~/vnit-chatbot-backups/2026-11-20-before-runbook-9/`, baseline in REPORT9.md |
| 1 | DONE | 886 pages imported as data/raw/site_*.txt; checks unchanged |
| 2 | DONE | bigger index measured, not better: backup index restored, pages kept in data/raw_site_crawl/ (§29) |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |

## Decisions

- Step 0: the runbook's list of "5 search misses" names `higher_sem_classes_start` and `gs_eligibility`, but both pass in the saved results now; `msc_tuition` fails instead. Step 3 works from the saved results (the 9 actual failures) and from chunk_ranks' "not reaching the LLM" list, which still includes `gs_eligibility` and `higher_sem_classes_start` at retrieval level.
- Step 0: `chunk_ranks.py` now measures 77 answerable questions (the README's 41/47 was before the 100-case set). The baseline is 69/77 within the top 7.
- Step 0: baseline per-question lists are in `../_trash/` (outside this repo, next to it), as the runbook says.

- Step 1: the boilerplate (40%-of-pages) filter was not applied: on the new files the repeated lines are profile headings, 0-7% of words.
- Step 1: `crawl.should_skip` applied as written; it skipped none of the new pages.
- Step 2: the near-duplicate rule (option b) was applied at import time rather than in query.py: same effect (the first crawl's copy wins), no change to the live search path.
- Step 2: none of the three tried versions met the keep rule, so the runbook's last resort was taken: restore the backup, move site_*.txt to data/raw_site_crawl/. Steps 3-7 work on the original index.
- Step 2: the corrective-step change (look at 6 pages, keep the best 2) was reverted with the step; it was only measured together with the bigger index.

## Baseline (no key)

- test_agentic: 54/54
- chunk_ranks: top 7 69/77, top 3 64/77, top 12 72/77
- fact_ranks: 15/18 in top 3
- evaluate: 16/19 right page in top 3
