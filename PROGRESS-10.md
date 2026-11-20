# Runbook 10 progress

Read this first after a restart; carry on from the first step not marked DONE, FAILED or SKIPPED.

| Step | Status | Note |
|---|---|---|
| 0 | DONE | tag `before-runbook-10`, backups, baseline 68/68, 73/77, 14/18, 16/19 |
| 1 | DONE | `discover-crawl` added 116 documents (115 selected, tier 0); existing entries unchanged |
| 2 | DONE | timeboxed at 4 h: 47 kept, 1 excluded (list of candidates), 1 empty, 4 failed, 62 still to do |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |

## Decisions

- Step 0: the runbook file itself was untracked; it is committed with Step 0.
- Step 1: the two new tests were written before Step 0's test run started, so the baseline test count is 68/68 (66 old + 2 new).
- Step 1: `count_new_documents.py` now calls the shared `crawl_links`/`crawl_candidates`, so its 116 and `discover-crawl`'s 116 are the same list by construction. People/procurement count 45 (was 44): link text kept to 200 characters, as `discover()` does.
- Step 1: `--only-new` reads every `data/documents/added_*.json`, not one dated file, so a later run on another day still finds them.
- Step 2: no old failures would be retried (every old selected document is in status.json), but `--only-new` was used anyway.
- Step 2: timebox hit with 62 of 115 not converted; the run moves on with the 47 kept, as the runbook says. The order was newest-first in tier 0, so the most recent fee/calendar notices are among those converted.
- Step 2: a converted recruitment-candidates refund list passed the old privacy rules; added the PERSON_LABEL density rule (flags only that document of all 446) rather than a title rule, since its title says "candidates" only as "in respect of candidates".
