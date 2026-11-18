# Runbook 8 progress

Step 0: DONE - repo created; Python 3.13.5, Git 2.52, Edge found; ablation runner not running
Step 1: DONE - 75 pages in 11 sections, 6 left out or special; 401 notices
Step 2: DONE - build_site.py builds 87 pages; no 40% boilerplate found; widget text and zero counters dropped
Step 3: DONE - home page: hero, 10 latest notices, news, quick links, director, events, rankings, emergency numbers

## Decisions

- The `claude` command is not installed on the laptop, so `run_overnight.sh` cannot run. The steps are done one after another in a single Claude Code session from the VS Code extension instead. Same runbook, same rules.
- Duplicate pages (identical text at two addresses): the shorter-named or main address is kept, the other listed in left_out.json.
- Menu titles: a short readable name is used where the crawled <title> is long or misspelt ("Departrnent"); the page text itself is untouched.
- Notice titles: "Next Next post: " prefixes picked up from link text are removed (navigation words, not content).
- Cleaning: the 40% boilerplate rule finds nothing (crawl was already clean), so it is kept but a small fixed list of widget controls ("Next slide", "Read more →", "vnit_web") and zero-valued animated counters are dropped instead.
- Broken sentences are rejoined (only whitespace between line pieces changes). The faithfulness check in Step 7 must therefore compare text with whitespace removed.
- "Home" is left out of the menu so it fits on one row at 1366 px; the institute name links home.
- Home "Scholarships" quick link opens notices.html?q=scholarship (no scholarship page exists in the crawl). notices.js must read ?q= into the search box.
- Home news skips headlines about lists of candidates (privacy) and one garbled Marathi headline.

## Next step should know
- Notice titles are the document's own title; a few are single words ("Physics", "Gallery"). The Notices page should show the page each was found on, so they make sense.

- Python: `~/anaconda3/python.exe` (3.13.5).
- Screenshots: use `bash tools/shot.sh <page> <png> <width> <height>` (handles Edge's own profile, its late PNG, and phone widths via a frame).
- Edge for screenshots: `/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`.
- Git identity in this repo is copied from vnit-chatbot (Doddi Shivanand).
- vnit-chatbot `git status --short` at Step 0: only ` M data/processed/answer_check.json`. Step 6 must leave it exactly like that.
- No ablation or 100-case runner is running (the 100-case run was halted on 14 Nov at 50 of 100 answered).
