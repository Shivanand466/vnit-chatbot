"""
Count the documents the website's full crawl links to that the chatbot has never seen.

The full crawl (../vnit-website/crawl/) reached ~1,600 pages; their Google Drive
and vnit.ac.in PDF links may include fee sheets, calendars or rules that
ingest_documents.py never discovered, because it only looked at the 81 pages of
the first crawl. Converting documents takes hours and the Drive key, so this
only counts them, read-only: nothing is downloaded, and inventory.json and
status.json are not changed.

Links and the selection are ingest_documents' own (links_on, crawl_candidates),
so the documents counted here are exactly the ones `discover-crawl` adds.

    ~/anaconda3/python.exe count_new_documents.py
"""
import json
import re
import sys

from ingest_documents import INVENTORY, PEOPLE_LISTS, PROCUREMENT, SITE_CRAWL, STATUS, crawl_candidates, crawl_links

SHOW = 20


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    found = crawl_links(SITE_CRAWL)
    new = {k: v for k, v in found.items() if k not in inventory}
    people = {k for k, v in new.items() if re.search(f"{PEOPLE_LISTS}|{PROCUREMENT}", v["link_text"], re.I)}
    chosen, _ = crawl_candidates(found, inventory, status)
    # Newest first: a 2026 fee notice matters more than a 2021 calendar.
    promising = sorted(chosen.values(), key=lambda v: (-max(map(int, re.findall(r"20[12]\d", v["link_text"])), default=0),
                                                       v["link_text"].lower()))
    drive = sum(1 for k in new if k.startswith("drive:"))

    print(f"Document links in the full crawl: {len(found)}")
    print(f"  already in inventory.json:     {len(found) - len(new)}")
    print(f"  new:                           {len(new)} ({drive} Google Drive, {len(new) - drive} vnit.ac.in PDFs)")
    print(f"  new, titled like lists of people or procurement (would be skipped): {len(people)}")
    print(f"  new titles about fees, calendar, hostel, scholarship, placement or rules,"
          f" not already read under another link: {len(promising)}")
    print(f"\nThe {SHOW} newest of those, by link text:")
    for v in promising[:SHOW]:
        print(f"  {v['link_text'][:80]:80s}  on {v['found_on'].replace('https://vnit.ac.in', '')[:60]}")


if __name__ == "__main__":
    main()
