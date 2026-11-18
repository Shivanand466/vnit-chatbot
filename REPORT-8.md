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

## Step 3. Home page

Built `templates/home.html` and `build_home()` in `build_site.py`. Every item is copied from a raw file or `notices.json`:

| Part | Copied from |
|---|---|
| Hero line | first sentence of `history.txt`: "Visvesvaraya National Institute of Technology, Nagpur is one of the thirty National Institutes of Technology in the country." |
| Buttons | Admissions → `admissions/admission.html`, Academic calendar → `academics/academic-calendar.html`, Ask the VNIT Assistant (opens the widget, Step 5) |
| Latest notices | the 10 newest in `notices.json`, with date and category; "All notices" → `notices.html` |
| News and events | the first 12 headlines under "📢 Latest VNIT News" in `home.txt`. Each one that has its own page, or appears on a crawled News listing page, links there; the rest are plain text. Headlines about lists of candidates and one Marathi headline that the crawl garbled (contains �) are skipped. |
| Quick links | Fees, Hostel, Academic calendar, Placements, Scholarships (opens Notices filtered to "scholarship"; there is no scholarship page in the crawl, only scholarship notices), Telephone directory, Contact |
| From the Director | name, title and the first two sentences of the bio in `director.txt`, with "Read more" → `about/director.html` |
| Upcoming events | the "🎯 Upcoming VNIT Events" list in `home.txt`, each with its 📅 date where the crawl gives one |
| VNIT Ranking | the three ranking lines at the end of `home.txt` |
| Emergency contacts | the line from `home.txt`, numbers as `tel:` links |

Looked at screenshots at 1366 px and at 390 px: two columns on a laptop and one column on a phone, no overlap, and the menu fits on one row at 1366 px. Step 7 retakes these properly.

**Done when:** home page builds: yes. Every item traces to a raw file or `notices.json`: yes (table above; Step 7's faithfulness check verifies it). Reads well at 1366 and 360–390 px: yes, by screenshot.

## Step 4. Every other page, plus Notices with search

- **Content pages (75):** each has breadcrumbs (Home › Section › Page), a left menu of the section's pages (it becomes a row of chips on a phone), the cleaned content and the Source line.
- **Department pages (13):** the same, plus a "Programmes offered" box built only from programme lines in that department's own file. Lines are kept when they start with B.Tech, M.Tech, Ph.D, M.Sc, B.Arch or MBA, are 70 characters or shorter, and don't mention admission; a short line is dropped when a fuller one starts with it. The department files contain **no email or phone number**, so no box has a contact part. Departments with no programme lines (Architecture, Chemical, Mechanical, Humanities) have no box.
- **Section index pages (11):** a card per page, showing the page title and its first sentence.
- **Notices (`notices.html`):**
  - All 401 notices in a table (date, title, category). Each title opens the document in a new tab, and a "Listed on" link (295 of 401) goes to the site page it was found on.
  - `assets/js/notices.js` adds a search box (all words must match) and category buttons, and reads `?q=` and `?category=` from the address. Without JavaScript, the tools stay hidden and all rows show.
- **Contact (`more/contact.html`):** Contact Us followed by the Telephone Directory page's text, each with its own Source line. Every number is exactly as crawled.
- **404 (`404.html`):** link home and the chat button. Its links use `/site/` because a server shows it at any address; that only matters under the chatbot server.

Notices search, tested in headless Edge (screenshots, then deleted):

| Address | Shown |
|---|---|
| `notices.html?q=hostel%20fees` | "20 of 401 notices", all hostel-fee documents |
| `notices.html?category=placements` | "16 of 401 notices", Placements button pressed (16 is the placements count from Step 1) |
| `notices.html?q=zzzz` | "0 of 401 notices" and "No notice matches. Try fewer words, or ask the VNIT Assistant." |

`python build_site.py`: `Built 89 pages into dist/`, no warnings.

**Done when:** every pages.json entry has a built page: yes, 75 of 75. Notices search filters correctly: yes (table above). Build warning-free: yes.

## Step 5. The VNIT Assistant chat widget

Built `assets/js/vnit-assistant.js` and `assets/css/vnit-assistant.css`, loaded on every page by `templates/base.html`. Every widget class starts with `va-` so it can't clash with the site's styles.

- **Opening and closing:** a round "Ask VNIT Assistant" button sits bottom-right. It opens a 400×600 panel, which is full screen below 600 px. Esc or the × button closes it. Focus moves to the question box on opening and back to the button on closing. `?assistant=open` in the address opens it on load (for screenshots), and so does any `[data-open-assistant]` element, such as the home page button and the footer button.
- **Suggested questions per page:** taken from HOW-TO-RUN §3.
  - Hostel pages: the vague "What is the hostel fee?" (it asks back with buttons), the first-year B.Tech boys fee, and the wifi question that it can't answer.
  - Academics: calendar dates. Admissions: tuition. Departments: Civil, Electrical and Mechanical questions. About and Administration: Director and Dean (Academic). Notices: scholarships.
- **Which server it talks to:** `window.VNIT_ASSISTANT_API` if a page sets it. Otherwise, when the page is served over http(s) under `/site/`, the same address's `/ask`. Otherwise `http://127.0.0.1:8000/ask`. There is no settings box.
- **Server not reachable:** "The VNIT Assistant isn't running. Start it with start_website.bat."
- **Conversation state:** `asked` and `profile` live in memory only (no localStorage, no cookies), exactly like the chat page. **They are forgotten when the visitor moves to another page.** This is accepted, and matches the chatbot's privacy rule.

Test, no server running: `tools/widget_test.html` loads `students/hostel.html?assistant=open` in a frame, types "What is the hostel fee?" and presses Ask. The screenshot shows the question, then "The VNIT Assistant isn't running. Start it with start_website.bat." with the mode "error"; the page itself is unaffected. At 390 px the panel fills the screen, with the three hostel suggestions.

Also dropped from page text in this step: photo file names that the crawl picked up from image sliders ("IMG-20240302-WA0016", "Oplus_131072 cultnite").

**Feature comparison with `vnit-chatbot/frontend/index.html`:**

| Chat page feature | Widget |
|---|---|
| Starter questions | yes, chosen per page (3) |
| Markdown answers via `renderAnswer`, everything escaped first with `escapeHtml` | yes, same code |
| `[1]` citations as superscripts | yes |
| Numbered sources as links, only `http(s)://` URLs made links | yes; a non-http source shows as plain text instead of `href="#"` |
| "Understood as" line | yes |
| Clarify choice buttons that set the profile and re-ask the original question with the same history | yes |
| "Clear my details" | yes (a button, shown only when details are set) |
| "How I found this" with the step kinds | yes, same labels |
| ✓ / ⚠ verification badge | yes |
| Mode note | yes |
| 👍/👎 calling `/feedback` | yes; not shown for direct, clarify or error answers (the chat page also shows them on errors) |
| "Searching…" then "Looking further…" after 12 s | yes |
| Error messages: server's `detail` / HTTP status | yes; "can't reach the server" now says the runbook's "isn't running" message |
| Follow-up history (last 3 questions) | yes |
| Enter sends, Shift+Enter new line, box grows | yes |
| Server address box (`#api-row`) | **no**, on purpose: no settings for visitors; the address is chosen automatically (above) |
| Dark mode | no; the site is light only (the runbook says dark mode isn't needed) |

**Done when:** the widget loads on every built page: it is in `base.html`, and Step 7 checks every page. With no server, asking shows the "isn't running" message, not a broken page: yes. Feature comparison: above.

## Step 6. Serve the website from the chatbot server

Changed `vnit-chatbot/api/main.py`:
- one sentence in the docstring about `/site/`;
- imports `RedirectResponse` and `StaticFiles`;
- `SITE = …/vnit-website/dist`;
- when `SITE` exists, `GET /site` redirects to `/site/` and `app.mount("/site", StaticFiles(directory=SITE, html=True))`.

Nothing else in the file changed. The Docker image has no `vnit-website`, so on Hugging Face nothing changes.

Added `vnit-chatbot/start_website.bat`: a copy of `start_chatbot.bat` that opens `http://127.0.0.1:8000/site/` (and says "website" in its messages). Key loading is unchanged.

Test with no key: `env -u GENAI_API_KEY timeout 170 python -m uvicorn api.main:app --host 127.0.0.1 --port 8010`. Healthy after about 36 s.

| Check | Result |
|---|---|
| `GET /site/` | 200, contains the demo banner |
| `GET /site` | redirected to `/site/`, 200 |
| `GET /site/notices.html` | 200, 401 notice rows |
| `GET /` | 200, still the old chat page (`<title>VNIT Chatbot</title>`) |
| `GET /site/no-such-page.html` | 404 with the site's "Page not found" page |
| `POST /ask` "Who is the Director of VNIT?" | `mode: "extractive (no GENAI_API_KEY set)"`, 1 source, answer starts "On "Who is the Director of VNIT?" — Director, VNIT, Nagpur says: Prof. (Dr.) Prem Lal Patel, President ISH & Director VNIT Nagpur…" |

The server stopped itself at the 170 s timeout, and port 8010 was confirmed free afterwards.

`cd pipeline && python test_agentic.py` (no key): **54/54 passed**.

Commit in vnit-chatbot, with only the two files added by name: `2db31f2 Serve the VNIT website at /site/ when it has been built`. Not pushed.

`git status --short` in vnit-chatbot afterwards: ` M data/processed/answer_check.json`, the same as at Step 0.

**Done when:** all checks in 3 and 4 pass: yes. `git status` shows only what it showed in Step 0: yes.
