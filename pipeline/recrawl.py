"""
Scheduled re-crawl (Data & Knowledge Pipeline, plan doc, step 6).

For every URL already in data/raw/*.txt: re-fetch it for real (via
fetch_utils.py, requests + BeautifulSoup), diff against what's stored, and
either update the file (content changed) or mark it stale (page no longer
reachable) -- so the agentic layer's recency tiebreak in agent.py has real
dates to work with instead of everything sharing one crawl date.

IMPORTANT FIRST-RUN CAVEAT: the 19 pages currently in data/raw/ were
originally fetched through Claude's WebFetch tool, which passes content
through a small summarizing model -- so that text is a paraphrase, not a
verbatim scrape. This script's fetch_utils.fetch_page() extracts real
verbatim text via BeautifulSoup. That means the FIRST time this runs,
expect most or all 19 pages to show as "changed" even if the live page
itself hasn't -- that's the extraction method improving, not 19
coincidental edits to the website. Don't read that first-run diff count as
a signal of anything; from the second run onward, diffs should reflect
real content changes.

Needs real internet to vnit.ac.in, which Claude's own tooling (cloud
sandbox + device-bridge shell) cannot reach -- see README.md. Run this via
RUNBOOK-FOR-CLAUDE-CODE.md on a machine with normal internet.
"""
import re
from datetime import date
from pathlib import Path

from fetch_utils import fetch_page

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def get_source_urls():
    """What we'd need to re-fetch -- reads existing files' SOURCE_URL headers."""
    urls = []
    for path in sorted(RAW_DIR.glob("*.txt")):
        if path.name.startswith("doc_"):
            continue  # documents are refreshed by ingest_documents.py, not re-scraped as web pages
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^SOURCE_URL:\s*(\S+)", text, re.MULTILINE)
        if match:
            urls.append((path, match.group(1)))
    return urls


def apply_refresh(path: Path, new_body: str, title: str):
    """Overwrite a raw file with freshly-fetched content and today's date,
    only if the body actually changed (avoids bumping FETCHED on no-op
    re-crawls, which would defeat the recency tiebreak's purpose)."""
    old_text = path.read_text(encoding="utf-8")
    old_body = old_text.split("---\n", 1)[-1].strip()
    if old_body == new_body.strip():
        return False  # unchanged, nothing to do

    source_url = re.search(r"^SOURCE_URL:\s*(\S+)", old_text, re.MULTILINE).group(1)
    header = f"SOURCE_URL: {source_url}\nTITLE: {title}\nFETCHED: {date.today().isoformat()}\n---\n"
    path.write_text(header + new_body.strip() + "\n", encoding="utf-8")
    return True


def mark_stale(path: Path):
    text = path.read_text(encoding="utf-8")
    if "STALE:" in text.splitlines()[0:4]:
        return  # already marked
    lines = text.splitlines()
    lines.insert(3, f"STALE: {date.today().isoformat()} (page no longer reachable at last re-crawl)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run():
    urls = get_source_urls()
    print(f"Re-crawling {len(urls)} known pages...\n")
    changed, unchanged, stale, errors = [], [], [], []

    for path, url in urls:
        try:
            title, text, content_type, raw_html = fetch_page(url)
        except Exception as e:
            mark_stale(path)
            stale.append((path.name, url, str(e)))
            print(f"  [STALE] {path.name} <- {url} ({e})")
            continue

        if raw_html is None:
            print(f"  [SKIP] {path.name} <- {url} (non-HTML: {content_type})")
            continue

        if apply_refresh(path, text, title or path.stem):
            changed.append((path.name, url))
            print(f"  [CHANGED] {path.name} <- {url}")
        else:
            unchanged.append((path.name, url))
            print(f"  [unchanged] {path.name}")

    print(f"\nDone. Changed: {len(changed)}. Unchanged: {len(unchanged)}. "
          f"Stale/unreachable: {len(stale)}.")
    if stale:
        print("Stale (see module docstring on the first-run caveat before panicking about 'changed' counts):")
        for name, url, err in stale:
            print(f"  {name} <- {url}: {err}")
    return changed, unchanged, stale


if __name__ == "__main__":
    run()
