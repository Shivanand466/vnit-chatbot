"""
Bring the website's full crawl of vnit.ac.in into the chatbot's data/raw.

The chatbot's own crawl kept 81 pages. The website project (../vnit-website)
later crawled every page vnit.ac.in lists -- about 1,600 -- and saved the HTML.
This reads that crawl and writes each new page as data/raw/site_<slug>.txt in
the same format the first crawl used, read by the same html_to_text, so the
chunker sees no difference between old and new pages.

Pages the chatbot already has are left alone (the 100 test cases were checked
against those files). Lists of people, near-empty pages, Hindi-only pages,
listing/archive pages and exact duplicates are skipped, with the reason counted.

    ~/anaconda3/python.exe import_site_crawl.py            # import
    ~/anaconda3/python.exe import_site_crawl.py --dry-run  # count only
"""
import argparse
import gzip
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import crawl
from fetch_utils import html_to_text
from ingest_documents import (BLANK_FORMS, PEOPLE_LISTS, PROCUREMENT, SKIP_PAGES,
                              looks_like_personal_data)

SITE_CRAWL = Path(__file__).parent.parent.parent / "vnit-website" / "crawl"
RAW_DIR = crawl.RAW_DIR
CRAWL_LABEL = "full-2026-11-19"
MIN_WORDS = 40

LISTING_PATHS = re.compile(r"/page/\d+|/tag/|/author/|/category/|/feed/?$|/attachment/|replytocom|[?&]s=", re.I)
LISTING_BODY = re.compile(r'<body[^>]*class="[^"]*\b(attachment|archive|search|blog|paged)\b', re.I)
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LETTER = re.compile(r"[^\W\d_]")


def normalise_url(url: str) -> str:
    """One spelling per page: https, no www, no query or fragment, no trailing slash,
    percent-encoding made uniform."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = quote(unquote(parts.path), safe="/:@!$&'()*+,;=-._~").rstrip("/")
    return f"https://{host}{path}"


def body_hash(text: str) -> str:
    return hashlib.sha1(re.sub(r"\s+", " ", text).strip().lower().encode("utf-8")).hexdigest()


def mostly_devanagari(text: str) -> bool:
    letters = len(LETTER.findall(text))
    return letters > 0 and len(DEVANAGARI.findall(text)) / letters > 0.5


def existing_pages():
    """(normalised URLs, body hashes) of everything already in data/raw."""
    urls, hashes = set(), set()
    for path in RAW_DIR.glob("*.txt"):
        header, _, body = path.read_text(encoding="utf-8").partition("---\n")
        m = re.search(r"^SOURCE_URL:\s*(\S+)", header, re.M)
        if m:
            urls.add(normalise_url(m.group(1)))
        hashes.add(body_hash(body))
    return urls, hashes


def skip_reason(url: str, html: str, title: str, text: str):
    """Why a crawled page should stay out of data/raw, or None to keep it."""
    if crawl.should_skip(url):
        return "crawl.should_skip"
    if LISTING_PATHS.search(url) or LISTING_BODY.search(html[:20000]):
        return "listing, archive or attachment page"
    if re.search(SKIP_PAGES, url):
        return "skipped section (stores, recruitment)"
    if re.search(PEOPLE_LISTS, title, re.I) or re.search(PROCUREMENT, title, re.I):
        return "title: list of people or procurement"
    if re.search(BLANK_FORMS, title, re.I) and not re.search(r"fee", title, re.I):
        return "title: blank forms"
    if len(text.split()) < MIN_WORDS:
        return f"under {MIN_WORDS} words"
    if mostly_devanagari(text):
        return "mostly Devanagari"
    if looks_like_personal_data(text):
        return "personal data"
    return None


def unique_path(slug: str, taken: set) -> Path:
    name, n = f"site_{slug}", 2
    while name in taken or (RAW_DIR / f"{name}.txt").exists():
        name, n = f"site_{slug}_{n}", n + 1
    taken.add(name)
    return RAW_DIR / f"{name}.txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count, write nothing")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    manifest = json.loads((SITE_CRAWL / "manifest.json").read_text(encoding="utf-8"))
    old_urls, seen_hashes = existing_pages()
    counts, imported, skipped, taken = Counter(), [], [], set()

    # Shortest URL first, so of two identical pages the shorter address is kept.
    entries = sorted(((e.get("final_url") or u, e) for u, e in manifest.items()
                      if e.get("status") == 200 and "file" in e), key=lambda x: (len(x[0]), x[0]))
    for url, entry in entries:
        if normalise_url(url) in old_urls:
            counts["already in data/raw"] += 1
            continue
        html = gzip.decompress((SITE_CRAWL / "html" / entry["file"]).read_bytes()).decode("utf-8", "replace")
        title, text = html_to_text(html)
        title = title or url
        reason = skip_reason(url, html, title, text)
        if reason is None and body_hash(text) in seen_hashes:
            reason = "same text as another page"
        if reason:
            counts[reason] += 1
            skipped.append((title, reason))
            continue
        seen_hashes.add(body_hash(text))
        counts["imported"] += 1
        imported.append(title)
        if not args.dry_run:
            path = unique_path(crawl.slugify(url), taken)
            header = (f"SOURCE_URL: {url}\nTITLE: {title}\nFETCHED: {entry['fetched']}\n"
                      f"CRAWL: {CRAWL_LABEL}\n---\n")
            path.write_text(header + text.strip() + "\n", encoding="utf-8")

    for reason, n in counts.most_common():
        print(f"{n:5d}  {reason}")
    rng = random.Random(20261120)
    print("\n10 imported titles:")
    for t in rng.sample(imported, min(10, len(imported))):
        print(f"  {t[:90]}")
    print("\n10 skipped titles:")
    for t, r in rng.sample(skipped, min(10, len(skipped))):
        print(f"  {t[:70]}  [{r}]")


if __name__ == "__main__":
    main()
