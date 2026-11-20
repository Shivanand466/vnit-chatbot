# Runbook 10 report: new documents, table rows, freeze and measure

## Good morning

(Written at the end, in Step 7.)

---

## Step 0. Baseline, tag and backups

- `git status` after `24792b0`: clean apart from the untracked `.claude/` and this runbook file (`RUNBOOK-10-DOCUMENTS-TABLE-ROWS-ABLATIONS.md`, committed with Step 0).
- Tag `before-runbook-10` created.
- Backups in `~/vnit-chatbot-backups/2026-11-20-before-runbook-10/`, sizes equal to the originals: `index.pkl` 30,444,574 B, `chunks.jsonl` 8,127,577 B, `facts.db` 8,753,152 B, `inventory.json` 297,623 B, `status.json` 107,866 B.
- `PY` (`~/anaconda3/python.exe`) and `PDFPY` (`~/.venvs/vnit-pdf/Scripts/python.exe`) exist; `import docling` works in `PDFPY`. `~/vnit-secrets.txt` exists and is non-empty (checked with `test -s`, not read).
- Baseline, no key (per-question lists in `../_trash/r10_baseline_*.txt`):

| Check | After Runbook 9 | Step 0 |
|---|---|---|
| Agent unit tests (`test_agentic.py`) | 66/66 | **68/68** (the 66 of Runbook 9 plus the 2 of Step 1, which were already written when this run started; all 66 old ones pass) |
| Answer passage reaches the LLM (`chunk_ranks.py`, top 7) | 73/77 | **73/77** (66/77 in the top 3, 74/77 in the top 12) |
| Answer passage in top 3 (`fact_ranks.py`) | 14/18 | **14/18** |
| Right page in top 3 (`evaluate.py`) | 16/19 | **16/19** |
| End to end (`answer_check.json`) | 97/100 | 97/100 (saved results, not re-asked) |

Not reaching the LLM at baseline: `placements` and `higher_sem_classes_start` (not in the top 12; both pass end to end, through the corrective step and the agent's tools), `holiday_holi` (rank 9), `companies_btech_2425` (not in the top 12).

**Done when:** tag and backups exist; Pythons, Docling and the key file are checked; the baseline table is here. **Met.**

## Step 1. The 116 documents added to the inventory, from the saved crawl

- New in `ingest_documents.py`:
  - `links_on` finds a page's document links; `discover()` now calls it, with the same rules as before.
  - `add_metadata` is shared by `discover()` and the new action.
  - `crawl_links` reads the saved crawl (read-only, nothing fetched).
  - `crawl_candidates` holds the selection that `count_new_documents.py` used to do itself; it now calls this.
  - `merge_inventory` only adds keys and writes through a temporary file that is then renamed.
  - New action `discover-crawl`, and a `--only-new` flag for `convert` and `plan` that limits them to the keys listed in `data/documents/added_*.json`.
- Run: `PDFPY ingest_documents.py discover-crawl`.
  - 5,098 document links in the crawl.
  - **116 added**, with 0 metadata errors.
  - Skipped: 529 already in the inventory; 4,375 not about fees, calendar, hostel, scholarship, placement or rules; 45 lists of people or procurement; 22 with the title of a document already known; 11 with the same title as another new link.
  - The count reproduces Runbook 9's 116. The one difference is 45 lists of people instead of 44, because link texts are now kept to 200 characters, as `discover()` keeps them, instead of 150.
- Check against the backup (script): the inventory had 599 entries and now has 715. **Every existing entry is unchanged** (keys and values compared). The new keys are exactly the 116 in `data/documents/added_2026-11-20.json`.
- `plan --only-new`: **115 of the 116 are in tier 0** and none in tiers 1 or 2.
  - The Summer 2027 fee instructions are in tier 0.
  - The one not selected is "Engineers India Limited (EIL) Scholarship to SC & ST students 2022 Batch only (Application…)": its title matches the blank-forms rule. The tiers were not changed.
  - No old document is left unprocessed, so `convert` would only pick up new ones; `--only-new` is used anyway, as a safeguard.
  - The newest 10 in conversion order:
    - Extension Notice for NSP Scholarship (2026-11-16)
    - S-27-Fee Notice Even Term – Academic Year 2026-27 – UG-PG
    - Fees Payment Instruction Summer 2027
    - SOP for Semester Fee Payment Summer 2027
    - Student Feedback Notice
    - Student Feedback SOP
    - Notice for Mandatory Submission of Online Course Feedback for W26
    - Notice for Extension of the Last Date for filling the Course Feedback
    - Notice – Refund of Caution Deposit…
    - National Overseas Scholarship (NOS) Scheme for ST students

  The full list is in `../_trash/r10_plan.txt`.
- New tests, no key and no internet:
  - `test_crawl_documents_skip_known_links_people_lists_and_other_topics` (a fake crawl: a known link isn't added again, a link seen twice is added once, a merit list and an off-topic title are skipped);
  - `test_inventory_merge_keeps_every_existing_entry` (a temporary inventory: existing entries unchanged even when offered a new value, re-adding adds 0, no temporary file left).

  Both pass.

**Done when:** existing entries unchanged plus about 116 new ones; plan output here. **Met.**
