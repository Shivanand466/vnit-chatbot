"""
Bounded BFS crawler to expand the corpus beyond the 19 pages fetched by
hand via WebFetch during the original pilot. Needs real internet (see
fetch_utils.py's docstring) -- run this via RUNBOOK-FOR-CLAUDE-CODE.md,
not inside Claude's own tooling.

Usage:
    python3 pipeline/crawl.py --max-pages 60 --max-depth 3

Writes one data/raw/<slug>.txt per newly-discovered page, in the same
SOURCE_URL/TITLE/FETCHED format chunk.py already expects -- existing files
for URLs already in data/raw/ are left untouched (use recrawl.py to refresh
those). After this finishes, re-run chunk.py + build_index.py + evaluate.py.
"""
import argparse
import re
from collections import deque
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from fetch_utils import fetch_page, extract_internal_links, is_allowed

START_URL = "https://vnit.ac.in"
ALLOWED_NETLOC = "vnit.ac.in"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# Paths not worth indexing as chatbot knowledge (logins, raw file downloads,
# infinite calendar/pagination traps). Extend this list as the crawl turns
# up more junk -- better to skip too little at first and prune than to
# under-crawl.
SKIP_PATH_PATTERNS = [
    r"/wp-admin", r"/wp-login", r"/feed/?$", r"/tag/", r"/page/\d+",
    r"e-samarth", r"eoffice", r"webmail",
    # Added 2026-09-21 per REPORT2.md's near-duplicate-URL finding from the
    # first real crawl: /index.php/... paths mirror the same content as their
    # clean-URL equivalents, and /category/... are listing pages, not content.
    r"/index\.php/", r"/category/",
]


def slugify(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", path) or "home"
    return slug[:80]


def should_skip(url: str) -> bool:
    return any(re.search(pat, url, re.IGNORECASE) for pat in SKIP_PATH_PATTERNS)


def already_have(url: str, existing_urls: set) -> bool:
    return url.rstrip("/") in existing_urls


def load_existing_urls():
    urls = set()
    for path in RAW_DIR.glob("*.txt"):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^SOURCE_URL:\s*(\S+)", text, re.MULTILINE)
        if m:
            urls.add(m.group(1).rstrip("/"))
    return urls


def save_page(url: str, title: str, text: str):
    slug = slugify(url)
    path = RAW_DIR / f"{slug}.txt"
    if path.exists():
        path = RAW_DIR / f"{slug}_{abs(hash(url)) % 10000}.txt"
    header = f"SOURCE_URL: {url}\nTITLE: {title}\nFETCHED: {date.today().isoformat()}\n---\n"
    path.write_text(header + text.strip() + "\n", encoding="utf-8")
    return path


def crawl(max_pages: int, max_depth: int):
    existing = load_existing_urls()
    visited = set(existing)  # don't re-fetch pages the pilot already has
    queue = deque([(START_URL, 0)])
    saved, skipped_robots, skipped_pattern, errors = [], [], [], []

    while queue and len(saved) < max_pages:
        url, depth = queue.popleft()
        url = url.rstrip("/")
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        if should_skip(url):
            skipped_pattern.append(url)
            continue
        if not is_allowed(url):
            skipped_robots.append(url)
            continue

        try:
            title, text, content_type, raw_html = fetch_page(url)
        except Exception as e:
            errors.append((url, str(e)))
            continue

        if raw_html is None:
            continue  # non-HTML (PDF etc.) -- not handled by this pass, see README

        if text and len(text.split()) >= 30:  # skip near-empty pages
            path = save_page(url, title, text)
            saved.append((url, title, path.name))
            print(f"[{len(saved)}/{max_pages}] saved {path.name} <- {url}")

        if depth < max_depth:
            for link in extract_internal_links(url, raw_html, ALLOWED_NETLOC):
                if link.rstrip("/") not in visited:
                    queue.append((link, depth + 1))

    print(f"\nDone. New pages saved: {len(saved)}. "
          f"Skipped (robots): {len(skipped_robots)}. "
          f"Skipped (pattern): {len(skipped_pattern)}. "
          f"Errors: {len(errors)}.")
    if errors:
        print("Errors:")
        for url, err in errors[:20]:
            print(f"  {url}: {err}")
    return saved, skipped_robots, errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=60)
    parser.add_argument("--max-depth", type=int, default=3)
    args = parser.parse_args()
    crawl(args.max_pages, args.max_depth)
