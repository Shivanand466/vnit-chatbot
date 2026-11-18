# VNIT website, with the VNIT Assistant built in (student project demo)

A copy of the VNIT Nagpur website's structure and content, rebuilt from the pages and documents our chatbot already crawled from vnit.ac.in. The VNIT Assistant chatbot is a floating chat window on every page.

**This is a demo, not the official VNIT website.** Every page says so in a banner at the top and links to the real site, https://vnit.ac.in. Every page is marked `noindex` so search engines leave it out. Every content page ends with a "Source" line linking to the vnit.ac.in page it was copied from. There are no logins, forms or payments, and no VNIT logo or photos.

Final-year project by Avinav, Nikhil, Shivanand and Vaibhav.

## How to run

1. **On this laptop:** double-click `vnit-chatbot\start_website.bat`.
   - Keep the black window open.
   - After about 30 seconds the site opens at `http://127.0.0.1:8000/site/`.
   - The orange chat button is in the bottom-right corner of every page.
   - The old chat page is still at `http://127.0.0.1:8000/`.
2. **On a phone, or for examiners:** double-click `vnit-chatbot\start_public_link.bat`, then add `/site/` to the end of the `.trycloudflare.com` link it prints.
3. **To rebuild after changing anything** (in Git Bash):
   ```
   cd vnit-website
   ~/anaconda3/python.exe build_site.py
   ```
   The server shows the new pages straight away; just refresh the browser.

Without a Groq key the chatbot still works, but in "extractive" mode: it shows the best matching passage instead of writing an answer. `start_website.bat` loads the key from `%USERPROFILE%\groq-key.txt`, the same way `start_chatbot.bat` does.

You can also open `dist\index.html` straight from the folder, without the server. The site works, and the chat button looks for the chatbot at `http://127.0.0.1:8000`.

## How it is built

Everything comes from the chatbot's crawl in `../vnit-chatbot/data/raw/` (81 pages and 406 documents). Nothing is written by hand.

| Step | Script | Writes |
|---|---|---|
| Which crawled page becomes which page of the site | `tools/inventory.py` | `content/pages.json` (75 pages in 11 sections), `content/left_out.json` (6 files that don't become ordinary pages, and why) |
| The notice list | `tools/notices.py` | `content/notices.json`: the 401 documents the chatbot converted and did not exclude as personal data, newest first |
| The site | `build_site.py` | `dist/`: 89 pages of plain HTML with relative links, plus `sitemap.json` |

**`build_site.py` copies, never rewrites.** It:
- drops the old site's widget text ("Next slide", "Read more →", animated counters that were crawled as 0, photo file names, empty tab names) and repeated lines;
- rejoins sentences the crawl broke over two adjacent lines;
- turns lines into headings, lists, tables and paragraphs;
- makes emails and phone numbers clickable;
- turns a line that is the exact link text of a crawled document into a link to that document.

It uses the Python standard library only: no installs, no frameworks, no web fonts and no CDNs, so it works offline.

Templates are in `templates/` (Python `string.Template`). Styles are in `assets/css/site.css` and `assets/css/vnit-assistant.css`. Scripts are in `assets/js/`: `site.js` runs the menu, `notices.js` runs the notice search, and `vnit-assistant.js` is the chat widget.

### After the chatbot's crawl is refreshed

```
cd vnit-website
~/anaconda3/python.exe tools/inventory.py      # stops and names any new page file that needs a place
~/anaconda3/python.exe tools/notices.py
~/anaconda3/python.exe build_site.py
~/anaconda3/python.exe tools/check_faithful.py # must say 0 not found in the crawl
```
If `inventory.py` stops at a new page file, add it to `PAGES` (or `LEFT_OUT`) in that script.

## How the chat widget finds its server

`assets/js/vnit-assistant.js` sends questions to the first of these that applies:
1. `window.VNIT_ASSISTANT_API`, if a page sets it;
2. the same server's `/ask`, when the site is served under `/site/` (by `start_website.bat` or the public link), so no extra setup is needed;
3. `http://127.0.0.1:8000/ask` otherwise (for example, `dist/index.html` opened from the folder).

If no server answers, it says: "The VNIT Assistant isn't running. Start it with start_website.bat."

The widget does everything the chatbot's own chat page does:
- follow-up questions, with "Understood as";
- clarifying buttons that remember your choice, and "Clear my details";
- numbered sources and "How I found this";
- the ✓/⚠ figure check and 👍/👎 feedback.

The conversation is kept in memory only, never in cookies or storage, so it starts again when you open another page.

## Checks

```
~/anaconda3/python.exe tools/check_links.py     # every link inside the site leads to a page that exists
~/anaconda3/python.exe tools/check_pages.py     # every page has the banner, noindex, footer credit, one <h1>, a Source line
~/anaconda3/python.exe tools/check_faithful.py  # every piece of text on the site is found in the crawl
bash tools/screenshots.sh                       # 12 screenshots into checks/ (headless Edge)
~/anaconda3/python.exe tools/smoke_test.py      # needs the chatbot server on port 8010; uses no Groq quota without a key
```
All three Python checks report zero problems.
