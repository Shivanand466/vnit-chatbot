# Runbook 8 report: the VNIT website with the chatbot built in

## Step 0. Preflight

- `python --version`: Python 3.13.5 (`~/anaconda3/python.exe`)
- `git --version`: git version 2.52.0.windows.1
- Headless Edge: found at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- `claude` command: not installed, so `run_overnight.sh` cannot run; the steps were done in one interactive session instead.

vnit-chatbot, `git status --short`:
```
 M data/processed/answer_check.json
```
vnit-chatbot, `git log --oneline -3`:
```
c9a3631 100-case check, first day: 13/13 new cases correct, 48/50 overall so far
392e7e0 Answer check grows to 100 cases, written the way students ask
b7d3375 Count quota fallbacks as unanswered in the ablations; README brought up to date
```
Last 3 lines of `data/processed/ablation_runs.log`:
```
  + clarify: [PASS] unanswerable_wifi  (tools: 2, check: verified)
  + clarify: [PASS] hostel_fee_girls  (tools: 0, check: verified)
  + clarify: [PASS] summer_term_fee  (tools: 1, check: unsupported)
```
`run_ablations.sh` process: not running (nor the 100-case runner, halted on 14 Nov).

**Done when:** repo exists with one commit: yes. PROGRESS-8 records Python, Git, Edge and the ablation state: yes.

## Step 1. Content inventory

Built `tools/inventory.py` (writes `content/pages.json` and `content/left_out.json`) and `tools/notices.py` (writes `content/notices.json`).

`python tools/inventory.py`:
```
81 raw page files: 75 pages, 6 left out or special
  About              5
  Administration     8
  Academics          3
  Admissions         2
  Departments        13
  Research           12
  Students           11
  Placements         1
  News and events    10
  Recruitment        5
  More               5
```
Left out or handled specially:

| Raw file | Why |
|---|---|
| `faculty_recruitment_2025_shortlisted_candidates.txt` | lists named individual candidates (privacy rule) |
| `recruitmen.txt` | identical text to `recruitment.txt` (same page at a second address) |
| `section_academics_notice_new.txt` | identical text to `notices.txt` |
| `index_php_category_events.txt` | identical text to `category_events.txt` |
| `home.txt` | becomes the home page |
| `notices.txt` | used on the home page and the Notices page |

`index_php_category_news.txt` and `index_php_category_news_events.txt` look alike but list different stories, so both are kept (News, and News and Events).

`python tools/notices.py`:
```
401 notices written (55 documents excluded or not converted)
  academics    144
  admissions   94
  other        92
  hostel       52
  placements   16
  recruitment  3
```
The 55 left out are the 33 the chatbot marked `personal_data`, 14 that failed to convert, 5 empty and 3 in Hindi only. Dates come from the document's own modified date (Google Drive) or the date the crawler recorded.

**Done when:** pages.json and left_out.json account for every raw page file (asserted): yes, 75 + 6 = 81. notices.json has no excluded document (asserted): yes. Counts and left-out list above: yes.

## Step 2. Layout, design and the build script

Built `build_site.py` (standard library only), `templates/base.html`, `templates/page.html`, `templates/section.html`, `assets/css/site.css` and `assets/js/site.js`.

- **Look:** demo banner, then the emergency-numbers line from `home.txt`, then a navy header with the institute name as text plus the Hindi name. The Hindi name, "विश्वेश्वरय्या राष्ट्रीय प्रौद्योगिकी संस्थान", is copied from the crawled documents, since no page file has it. Under that is a menu of 11 section dropdowns plus Notices. Pages have a white content area, one warm accent colour, system fonts, and a footer with the postal address, phone and email copied from `contact_us.txt`. No logo file, so no logo is shown.
- **Menu:** dropdowns open on hover and on click or Enter, and Esc closes them. Below 900 px the menu becomes a "Menu" button.
- **Links:** every link inside the site is relative, so `dist/index.html` opens straight from the folder.
- **Cleaning** (`clean_lines`):
  - Drops the header.
  - Drops boilerplate: **no line appears in 40% or more of the 77 page files**, so nothing is dropped this way. The crawler had already removed the menus.
  - Collapses repeated lines.
  - Rejoins sentences the crawl broke over two lines: a line starting in lower case or with punctuation, an unclosed bracket, or a line ending in "of", "the" and similar words.
  - Drops the old site's widget controls: "Previous slide", "Next slide", "Read more →", "View More", the author tag "vnit_web".
  - Drops the animated counters that were crawled before they counted up ("Faculty 0", "STUDENTS 0"). Those zeros are wrong, not content.
- **Turning lines into HTML** (`to_html`):
  - A short line followed by a long one becomes a heading.
  - Runs of `|` lines become tables. Page files have almost none, so this rarely applies.
  - Runs of names starting "Dr./Prof./Shri…" become one card per person.
  - Other runs of short lines become a plain list; long lines become paragraphs.
  - Emails and phone numbers become `mailto:`/`tel:` links.
  - **A line whose text is exactly the link text of a crawled document from that page becomes a link to that document** (opens in a new tab). For example, every "HOSTEL FEES FOR …" line on Hostel Fees opens its PDF. Documents marked personal data are never linked.
- **Screenshots:** `tools/shot.sh` takes them with headless Edge. Edge needs its own profile folder, writes the PNG a few seconds after it returns, and cannot make a window narrower than about 500 px, so phone widths load the page inside a 390 px frame (`tools/phone_frame.html`).

`python build_site.py`:
```
No line is in 40% or more of page files; nothing dropped as boilerplate.
Built 87 pages into dist/
```
87 = 75 content pages + 11 section index pages + the home page (a placeholder until Step 3).

**Done when:** builds without errors: yes. `dist/index.html` exists: yes. At least one page per section: yes, every section folder has its pages plus `index.html`. Dropped-boilerplate list and page count: above.
