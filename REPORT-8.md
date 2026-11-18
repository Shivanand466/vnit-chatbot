# Runbook 8 report: the VNIT website with the chatbot built in

## Good morning

**What was built.**
- A copy of the VNIT website with 89 pages: home, 75 content pages in 11 menu sections, section overview pages, a searchable list of 401 notices, contact and a "not found" page.
- It is built entirely from the pages and documents the chatbot already crawled from vnit.ac.in. A check confirms that every one of its 6,987 pieces of text is copied from the crawl.
- The VNIT Assistant is a chat button in the corner of every page, with everything the chatbot's own chat page has: follow-ups, the clarifying buttons, sources, "How I found this", the ✓ check and 👍/👎.

**Steps** (from PROGRESS-8.md): **all ten are DONE**, none PARTIAL or FAILED.

| Step | Result |
|---|---|
| 0 | New repo `vnit-website/`, tools found (Python 3.13.5, Git, Edge) |
| 1 | 75 pages in 11 sections; 6 files left out or special, each with a reason; 401 notices |
| 2 | `build_site.py`, design, menu, phone layout |
| 3 | Home page: notices, news, quick links, Director, events, rankings, emergency numbers |
| 4 | All pages, department programme boxes, Notices search, Contact, 404 |
| 5 | Chat widget on every page |
| 6 | The chatbot server shows the site at `/site/`; `start_website.bat`; chatbot tests 54/54 |
| 7 | 0 broken links, 0 page problems, 0 text not found in the crawl, screenshots, smoke test passed |
| 8 | Phone fixes, fee-sheet headings, empty tabs removed; colour contrast all at least 5.2:1 |
| 9 | README and this report |

**The demo in 5 clicks:**
1. Double-click `vnit-chatbot\start_website.bat`. After about 30 seconds the home page opens at `http://127.0.0.1:8000/site/`.
2. Menu **Students → Hostel Section**.
3. Click the orange **Ask VNIT Assistant** button (bottom right).
4. Click the suggested question **"What is the hostel fee?"**. It asks back "Which programme are you asking about?"
5. Click **B.Tech**, then **Girls**. The answer appears with its source, "How I found this" and the ✓ check.

With your Groq key loaded, the answer is written in full. Without it, it quotes the best matching passage.

**What still doesn't work, or isn't there:**
- **The conversation starts again when you change page.** This is on purpose: it is kept in memory only, like the chat page, for privacy.
- **Without the key, answers are quoted passages**, and sometimes from a near-identical document. In last night's test, after "B.Tech, Girls" it quoted the B.Arch girls fee sheet. Load the key for the demo.
- On a phone, long breadcrumbs wrap so that "›" starts a line. Minor.

**Missing content** (not in the crawl, so left out rather than invented):
- No department page in the crawl has an email or phone number, so the department boxes show programmes only. Architecture, Chemical, Mechanical and Humanities have no programme lines either, so they have no box.
- The department tabs (PEOs, POs, PSOs, Department Stats) were never opened by the crawler, so their contents are missing. The tab names were removed.
- The old site's animated numbers ("Faculty", "Students", "Publications") were crawled as 0 and are left out.
- There is no Scholarships page in the crawl. The home page's Scholarships link opens the Notices page searched for "scholarship".
- No logo or photos (runbook rule). To add the logo if your guide approves, put `logo.png` in `vnit-website/assets/img/` and rebuild.
- The faculty recruitment shortlist page is left out, because it lists named candidates. 55 documents are not on the Notices page: 33 marked as personal data, 14 failed to convert, 5 empty, 3 in Hindi only.

**To put the code on GitHub** (optional; nothing has been pushed):
- **The website repo** is new and has no GitHub remote yet. Create an empty repository on github.com (for example `vnit-website`), then, in Git Bash:
  ```
  cd ~/OneDrive/Desktop/LIBRARY/FYP/VNIT-Website-Chatbot/vnit-website
  git remote add origin https://github.com/<your-username>/vnit-website.git
  git push -u origin master
  ```
- **The chatbot repo** has one new commit, `2db31f2` (serve the site at `/site/`):
  ```
  cd ../vnit-chatbot && git push
  ```
  Pushing it also runs the Hugging Face workflow, which skips itself without `HF_TOKEN`. The Hugging Face copy has no `vnit-website` folder, so nothing changes there.

**For the slides:** add a slide **"Built into the website"** after slide 11. Use the screenshot `checks/home-assistant-desktop.png` (home page with the assistant open) or `checks/demo-hostel-clarify-desktop.png` (hostel page, after clicking B.Tech and Girls), with one line: "The same chatbot, as a button on every page of a VNIT-style website built only from the crawled pages: 89 pages, 0 sentences not found in the source."

**If you want it in HOW-TO-RUN.md**, this paragraph can be pasted into `vnit-chatbot/HOW-TO-RUN.md` after section 2b (the runbook kept the chatbot's docs read-only):

> ## 2c. The chatbot inside a VNIT-style website (optional)
>
> Double-click `start_website.bat` instead of `start_chatbot.bat`. After about 30 seconds a copy of the VNIT website opens at `http://127.0.0.1:8000/site/`, built only from the pages the chatbot crawled, with an orange **Ask VNIT Assistant** button in the corner of every page. It is the same chatbot, with the same answers, sources and clarifying buttons. For a phone, use `start_public_link.bat` and add `/site/` to the end of its link. The site lives in the `vnit-website` folder next to this one; see its README to rebuild it.

---

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

## Step 7. Checks: links, faithfulness, screenshots, chatbot smoke test

All in `tools/`, so they can be re-run: `check_links.py`, `check_pages.py`, `check_faithful.py`, `screenshots.sh` (with `shot.sh`, `widget_shot.sh`, `phone_frame.html`, `widget_test.html`) and `smoke_test.py`.

### Links (`python tools/check_links.py`)
```
89 pages, 9697 internal links, 1296 external links
     552  drive.google.com
     346  tel:
     229  vnit.ac.in
     169  mailto:
0 broken internal links
```
The first run found **267 broken links**: three footer links on every page, written `$rootmore/contact.html`. The template engine read `$rootmore` as one unknown name. Fixed in `build_site.py`.

### Required parts of every page (`python tools/check_pages.py`)
```
89 pages checked (75 content pages), 0 problems
```
It checks for a title, the demo banner and its link, noindex, the footer credit, the widget script, exactly one `<h1>`, the Source line on content pages, and nothing loaded from another domain. The first run flagged Student Activity Clubs: its source address really is `http://vnit.ac.in/…` and the check only allowed `https://`, so the check was corrected.

### Faithfulness (`python tools/check_faithful.py`)
```
89 pages, 7018 pieces of text checked, 0 not found in the crawl
```
- **What it does:** every piece of visible text in `<main>` (paragraphs, list items, cells, headings, cut at `<br>` and spans) must appear in that page's raw file(s), comparing with whitespace removed. Notice rows are checked against `notices.json`. The allow-list holds only the site's own labels and section names.
- **First run: 56 misses.** Most were section names in breadcrumbs (now allow-listed as site labels), but **6 were real build bugs**: sentences glued together across lines that were not next to each other in the crawl, because a repeated line between them had been dropped. Fixed in `clean_lines`: lines are only rejoined when they are adjacent in the raw file.
- **The check works:** adding the made-up sentence "The hostel fee is Rs 1 for everyone." to Hostel Fees made it report `NOT IN CRAWL: The hostel fee is Rs 1 for everyone.`; removing it brought it back to 0.

### Screenshots (`bash tools/screenshots.sh`, headless Edge)
Home, CSE department, Hostel Fees, Notices, Contact, and Home with the widget open, each at 1366×900 and 390×844, in `checks/` (PNG files are not committed). Every one was opened and looked at.

Visible problems:
1. **Phone: the "Ask VNIT Assistant" button covers the last lines of text** at the bottom of every page (notices table, contact page, department page).
2. **Phone: the Notices table is wider than the screen**, and the Category column is cut off. It does scroll sideways inside its box, but it looks broken.
3. **Hostel Fees: the group labels** ("Hostel Fees Estimate and Demand Note for UG Students", "… for PG Students") look like ordinary list items, not headings over their fee sheets.
4. **Department pages: the old site's tab names** ("PO's / PEO's", "PEO's", "PO's", "PSO's", "Department Stats") appear as a list with nothing under them. Their contents were inside tabs the crawler did not open. The text is faithful but looks empty.
5. Phone: long breadcrumbs wrap so the "›" starts a line (minor).
6. Laptop: the floating button sits over the bottom-right corner of the home page's right column while scrolling (minor; it's a floating button).

No overlapping text, no cut-off menus, and the widget opens full screen on a phone as intended.

### Chatbot smoke test, no key (`python tools/smoke_test.py`, server on 8010 started as in Step 6)
```
GET /site/: ok, banner and widget script present

Q: Who is the current Director of VNIT?
   mode: extractive (no GENAI_API_KEY set) | sources: 1
   answer: 'On "Who is the current Director of VNIT?" — Director, VNIT, Nagpur says: Water Resources Society, and Institution of Civil Engineers, India. He has been instrumental in setting up a Centre of Excellen'

Q: What is the email of the Dean (Academic)?
   mode: extractive (no GENAI_API_KEY set) | sources: 1
   answer: 'On "What is the email of the Dean (Academic)?" — Deans says: Dr. Ratnesh Kumar Dean (Planning & Development) Email: deanp_f@vnit.ac.in Dr.'

Q: When do classes start for first year B.Tech students in Winter 2026?
   mode: extractive (no GENAI_API_KEY set) | sources: 1
   answer: 'On "When do classes start for first year B.Tech students in Winter 2026?" — ACADEMIC CALENDAR (Winter 2026) for First Year UG (B.Tech/B.Arch) says: conducting classes of first year UG courses. | Comme'

Q: What is the hostel fee?
   mode: clarify | choices: ['B.Tech', 'B.Arch', 'M.Sc', 'Ph.D']
   answer: 'Which programme are you asking about?'

smoke test PASSED
```
Without the key, the chatbot quotes the best passage instead of writing an answer, so the passages above are the right pages but not always the right sentence. That is expected. With the key, the same questions are answered properly (see the chatbot's own answer check).

**The full demo click path through the widget, on the real server:**
1. `tools/widget_test.html` was served from the same server for this one test (a temporary copy, removed afterwards), opened `/site/students/hostel.html?assistant=open` and asked "What is the hostel fee?".
2. It clicked **B.Tech**, then **Girls**.
3. The screenshot (`checks/demo-hostel-clarify-desktop.png`) shows the answer with its source chip, "How I found this (5 steps)", the mode note, 👍/👎 and "Clear my details".

Without the key, the quoting mode picked the B.Arch girls fee sheet. That is a limit of no-key mode, not of the widget.

The server stopped itself at its 170 s timeout.

**Done when:** links, pages and faithfulness pass with zero problems: yes (0, 0, 0). Screenshots exist and were looked at: yes, 12 plus the demo one. Smoke test results above: yes.

## Step 8. Polish from the screenshots

| Problem from Step 7 | Before | After |
|---|---|---|
| 1. Phone: the chat button covers text | wide "Ask VNIT Assistant" pill over the last lines | a 56 px round button on phones (its label is still read out by screen readers); extra space under the content and footer, so the last lines scroll clear of it |
| 2. Phone: Notices table too wide | Category column cut off, table scrolls sideways | Category column hidden below 600 px (the category buttons still filter); the date wraps, so the table fits at 390 px |
| 3. Hostel Fees group labels look like list items | "Hostel Fees Estimate and Demand Note for UG Students" in the list | now a heading over its fee-sheet links. The rule is general: a plain line followed by two or more document links becomes a heading |
| 4. Department pages: empty tab names | "PO's / PEO's", "PEO's", "PO's", "PSO's", "Department Stats" listed with nothing under them | dropped as widget text. Checked first: in every department file these lines are followed only by other tab names or by the zero counters. "Vision" and "Mission" do have text, so they stay |
| 5. Phone: breadcrumb wrap | "›" starting a line | **still there**; minor, left as is |
| 6. Laptop: floating button over the home page's right column | — | **left as is**: it is a floating button, and it moves with the scroll |

Also checked in this step:
- **Phone menu:** a test page clicked "Menu" then "Students" at 390 px. The screenshot shows the full-width menu with the Students pages listed under it.
- **Colour contrast:** worked out for every text/background pair in `site.css` and `vnit-assistant.css` (links, buttons, chips, banners, footer, badges, widget small print). The lowest is 5.22:1 (widget small text); none is below 4.5:1.
- **Widget tidy-up:** the zero-width space in the widget-text list is now written `​` in the code instead of an invisible character.

All of Step 7's checks were re-run after the fixes, and the screenshots were retaken and looked at again:
```
0 broken internal links
89 pages checked (75 content pages), 0 problems
89 pages, 6987 pieces of text checked, 0 not found in the crawl
```
6987 pieces instead of 7018, because the empty tab names are gone.

**Done when:** every Step 7 check still passes: yes. Before/after list: above.

## Step 9. README, how-to-run and this report

- `vnit-website/README.md`:
  - what the site is and that it is a demo, not the official site;
  - **How to run** (`start_website.bat`, the public link plus `/site/`, and rebuilding);
  - how it is built from the crawl (`tools/inventory.py`, `tools/notices.py`, `build_site.py`) and how to rebuild after the crawl is refreshed;
  - how the widget finds its server;
  - the checks.
- The "Good morning" section at the top of this report, including the paragraph to paste into `vnit-chatbot/HOW-TO-RUN.md` (the chatbot's README and HOW-TO-RUN were not edited).

**Done when:** README and REPORT-8 complete: yes. Every step's line in PROGRESS-8 filled in: yes (0 to 9, all DONE).
