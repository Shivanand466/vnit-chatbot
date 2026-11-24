# VNIT website, with the VNIT Assistant built in (student project demo)

A copy of the whole VNIT Nagpur website: every page vnit.ac.in lists, including each department's and section's own sub-site, at the same addresses and with the same menus. The VNIT Assistant chatbot is a floating chat window on every page.

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

Three steps, each a script. Nothing on the site is written by hand.

| Step | Script | Writes |
|---|---|---|
| 1. Fetch every page | `tools/crawl_site.py` | `crawl/html/` (each page's HTML, gzipped) and `crawl/manifest.json` |
| 2. Keep each page's own content, and the menus | `tools/extract.py` | `content/site.json`, `content/pages/`, `content/menus.json`, `content/skipped.json` |
| 3. Build the site | `build_site.py` | `dist/`: one folder per page, at the same address as on vnit.ac.in, plus `sitemap.json` |

The notice list (`/notices/`) still comes from the chatbot's documents (`tools/notices.py`), and the home page from the chatbot's crawl of the home, history and director pages.

**Step 1, the crawl.** The crawler finds pages in vnit.ac.in's own WordPress sitemaps: the main site plus 17 sub-sites (sections such as Academics, Hostel and T&P, and departments such as CSE and Civil). The departments without a sitemap (Mining, CVLSI, Architecture, Physics, Metallurgy) are found by following their links. It obeys robots.txt, waits a second between pages and can be stopped and resumed. The crawl of 2026-11-19 saved 1,628 pages; 22 addresses failed, almost all of them pages vnit.ac.in itself reports as missing (404).

**Step 2, extraction.** For each page the extractor keeps only the page's own content (headings, paragraphs, lists, tables, links) and drops the site header, footer, scripts, images, forms and sliders' duplicate copies. Text is never changed. It also brings back what the plain text crawl lost: tab contents, and the real numbers behind animated counters ("Faculty 22", not "Faculty 0"). It copies the main menu and each sub-site's own menu with all their levels. Pages left out, each with its reason in `content/skipped.json`:
- 48 that redirect to (or are the same as) another page;
- 18 pages of a WordPress theme's demo content left installed in the Civil sub-site (placeholder text about an imaginary city, example.com addresses);
- 2 pages that list named candidates (privacy);
- 1 test post ("test09.11.26").

**Step 3, the build.** `build_site.py` puts each page at its real address (`vnit.ac.in/engineering/cse/faculty/` becomes `dist/engineering/cse/faculty/index.html`) with the real main menu, the sub-site's own menu at the side, breadcrumbs and a Source line. Links between copied pages stay on the demo site; links to pages that were not copied (and to PDFs) go to vnit.ac.in. It uses the Python standard library only: no installs, no web fonts, no CDNs, so it works offline.

Things the demo does not copy, on purpose:
- **VNIT's logo and photos.** 22 pages on vnit.ac.in are only pictures (mostly newspaper clippings); their copy says how many pictures there are and links to the original.
- **Empty pages.** 69 pages are empty on vnit.ac.in itself (menu headings such as "Administration"); their copy says so and links to the original.
- **Logins, forms and payments.** Online Payment, e-Samarth and e-Office link to the real portals.

Templates are in `templates/` (Python `string.Template`). Styles are in `assets/css/site.css` and `assets/css/vnit-assistant.css`. Scripts are in `assets/js/`: `site.js` runs the menu, `notices.js` runs the notice search, and `vnit-assistant.js` is the chat widget.

### To refresh the copy from vnit.ac.in

```
cd vnit-website
~/anaconda3/python.exe tools/crawl_site.py           # about 3 hours for a full crawl; resumable
cd tools && ~/anaconda3/python.exe extract.py && cd ..   # about 12 minutes
~/anaconda3/python.exe tools/notices.py
~/anaconda3/python.exe build_site.py                 # under a minute
~/anaconda3/python.exe tools/check_faithful.py       # must say 0 not found in the crawl
```
The crawler skips pages it already saved. To fetch everything fresh, move `crawl/` to `_trash/` first.

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
~/anaconda3/python.exe tools/check_faithful.py  # every piece of text is found in the HTML vnit.ac.in sent for that page
bash tools/screenshots.sh                       # 16 screenshots into checks/ (headless Edge)
~/anaconda3/python.exe tools/smoke_test.py      # needs the chatbot server on port 8010; uses no Groq quota without a key
```
All three Python checks report zero problems (1,562 pages, 200,125 pieces of text).
