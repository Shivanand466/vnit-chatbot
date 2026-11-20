"""
Count the documents the website's full crawl links to that the chatbot has never seen.

The full crawl (../vnit-website/crawl/) reached ~1,600 pages; their Google Drive
and vnit.ac.in PDF links may include fee sheets, calendars or rules that
ingest_documents.py never discovered, because it only looked at the 81 pages of
the first crawl. Converting documents takes hours and the Drive key, so this
only counts them, read-only: nothing is downloaded, and inventory.json and
status.json are not changed.

Links are found as ingest_documents.discover() finds them (same Drive-id rule,
same vnit.ac.in .pdf rule), so a document counted as new here is one discover()
would add.

    ~/anaconda3/python.exe count_new_documents.py
"""
import gzip
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import drive_utils as du
from ingest_documents import INVENTORY, PEOPLE_LISTS, PROCUREMENT, TIER0_WORDS

SITE_CRAWL = Path(__file__).parent.parent.parent / "vnit-website" / "crawl"
SHOW = 20


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def links_on(url: str, html: str):
    """(key, url, link text) for each document linked from one page."""
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        link = urljoin(url, a["href"].split("#")[0])
        fid = du.drive_file_id(link)
        if fid:
            yield f"drive:{fid}", f"https://drive.google.com/file/d/{fid}/view", a.get_text(" ", strip=True)
        elif urlparse(link).netloc == "vnit.ac.in" and urlparse(link).path.lower().endswith(".pdf"):
            yield f"web:{link}", link, a.get_text(" ", strip=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    manifest = json.loads((SITE_CRAWL / "manifest.json").read_text(encoding="utf-8"))
    found = {}
    for url, entry in manifest.items():
        if "file" not in entry:
            continue
        html = gzip.decompress((SITE_CRAWL / "html" / entry["file"]).read_bytes()).decode("utf-8", "replace")
        for key, link, text in links_on(entry.get("final_url") or url, html):
            if key not in found or (text and not found[key]["text"]):
                found[key] = {"url": link, "text": text[:150], "found_on": url}

    new = {k: v for k, v in found.items() if k not in inventory}
    people = {k for k, v in new.items() if re.search(f"{PEOPLE_LISTS}|{PROCUREMENT}", v["text"], re.I)}
    useful = {k: v for k, v in new.items() if k not in people}
    # The same document is often linked both from Drive and as a vnit.ac.in PDF,
    # so a link whose text is the title of a document already read is not new.
    status = json.loads((INVENTORY.parent / "status.json").read_text(encoding="utf-8"))
    known = {norm(v.get("title", "")) for v in status.values()} | {norm(v.get("link_text", "")) for v in inventory.values()}
    by_title = {}
    for v in useful.values():
        if re.search(TIER0_WORDS, v["text"], re.I) and norm(v["text"]) not in known:
            by_title.setdefault(norm(v["text"]), v)
    # Newest first: a 2026 fee notice matters more than a 2021 calendar.
    promising = sorted(by_title.values(), key=lambda v: (-max(map(int, re.findall(r"20[12]\d", v["text"])), default=0),
                                                         v["text"].lower()))
    drive = sum(1 for k in new if k.startswith("drive:"))

    print(f"Document links in the full crawl: {len(found)}")
    print(f"  already in inventory.json:     {len(found) - len(new)}")
    print(f"  new:                           {len(new)} ({drive} Google Drive, {len(new) - drive} vnit.ac.in PDFs)")
    print(f"  new, titled like lists of people or procurement (would be skipped): {len(people)}")
    print(f"  new titles about fees, calendar, hostel, scholarship, placement or rules,"
          f" not already read under another link: {len(promising)}")
    print(f"\nThe {SHOW} newest of those, by link text:")
    for v in promising[:SHOW]:
        print(f"  {v['text'][:80]:80s}  on {v['found_on'].replace('https://vnit.ac.in', '')[:60]}")


if __name__ == "__main__":
    main()
