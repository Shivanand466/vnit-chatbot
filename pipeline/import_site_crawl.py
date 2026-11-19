"""
Turn the website's full crawl of vnit.ac.in into chatbot page files.

The chatbot's own crawl kept 81 pages. The website project (../vnit-website)
later crawled every page vnit.ac.in lists -- about 1,600 -- and saved the HTML.
This reads that crawl and writes each new page as data/raw_site_crawl/site_<slug>.txt
in the same format the first crawl used, read by the same html_to_text, so the
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
# Not data/raw: measured on 20 Nov 2026 (EXPERIMENTS-LOG §29), adding these pages to
# the index did not bring any test answer to the AI and pushed some out, so they are
# kept here, where chunk.py does not read them. Move them into data/raw to try again.
OUT_DIR = RAW_DIR.parent / "raw_site_crawl"
CRAWL_LABEL = "full-2026-11-19"
MIN_WORDS = 40

LISTING_PATHS = re.compile(r"/page/\d+|/tag/|/author/|/category/|/feed/?$|/attachment/|replytocom|[?&]s=", re.I)
LISTING_BODY = re.compile(r"\b(attachment|archive|search|blog|paged)\b", re.I)
BODY_TAG = re.compile(r"<body[^>]*>", re.I)
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
    """(normalised URLs, body hashes, page shingles) of what was in data/raw before
    this import. Earlier imports (site_*.txt) are not counted: run this after
    moving them out, so re-running gives the same result."""
    urls, hashes, pages = set(), set(), []
    for path in RAW_DIR.glob("*.txt"):
        if path.name.startswith("site_"):
            continue
        header, _, body = path.read_text(encoding="utf-8").partition("---\n")
        m = re.search(r"^SOURCE_URL:\s*(\S+)", header, re.M)
        if m:
            urls.add(normalise_url(m.group(1)))
        hashes.add(body_hash(body))
        if not path.name.startswith("doc_"):
            pages.append(shingles(body))
    return urls, hashes, pages


def skip_reason(url: str, html: str, title: str, text: str):
    """Why a crawled page should stay out of data/raw, or None to keep it."""
    if crawl.should_skip(url):
        return "crawl.should_skip"
    body = BODY_TAG.search(html)  # comes after a long <head>, so search the whole page
    if LISTING_PATHS.search(url) or (body and LISTING_BODY.search(body.group())):
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


def sub_site(url: str) -> str:
    """The part of vnit.ac.in a page belongs to: "section/tnp", "engineering/cse", "arch" or ""."""
    parts = urlsplit(url).path.strip("/").split("/")
    if parts[0] in ("section", "engineering", "basic_science") and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0] if parts[0] == "arch" else ""


TITLE_SPLIT = re.compile(r"\s+[–—|-]\s+")


def strip_site_names(pages: list):
    """Drop a sub-site's name from the end of its page titles, in place.

    "About Us – VNIT Nagpur – Training & Placement Department" becomes "About Us".
    With the name left on, every T&P page matched a placement question by title,
    and the T&P front page fell from near the top of the title search to 21st.
    A name is an ending shared by at least 40% (and 3) of a sub-site's titles;
    front pages keep their title, which is the sub-site's name.
    """
    groups = {}
    for page in pages:
        groups.setdefault(sub_site(page["url"]), []).append(page)
    for site, members in groups.items():
        for _ in range(3):  # "– VNIT Nagpur – Hostel Section" is two endings
            endings = Counter(TITLE_SPLIT.split(p["title"])[-1] for p in members
                              if TITLE_SPLIT.search(p["title"]))
            if not endings:
                break
            name, count = endings.most_common(1)[0]
            if count < 3 or count < 0.4 * len(members):
                break
            for p in members:
                parts = TITLE_SPLIT.split(p["title"])
                if len(parts) > 1 and parts[-1] == name and sub_site(p["url"]) == site \
                        and urlsplit(p["url"]).path.strip("/") != site:
                    p["title"] = p["title"][:p["title"].rfind(name)].rstrip(" –—|-")


def shingles(text: str) -> set:
    words = re.sub(r"\s+", " ", text).lower().split()
    return {" ".join(words[i:i + 5]) for i in range(max(1, len(words) - 4))}


def near_duplicate(sh: set, kept: list) -> bool:
    """Word 5-gram overlap above 0.8 with a page already kept (old or new). The
    same page copied into two sub-sites ("Placement Policy For Companies" under
    both T&P and Hostel) otherwise appears twice and takes two places."""
    for other in kept:
        small, big = sorted((len(sh), len(other)))
        if small < 0.8 * big:
            continue
        if len(sh & other) / len(sh | other) > 0.8:
            return True
    return False


def unique_path(slug: str, taken: set) -> Path:
    name, n = f"site_{slug}", 2
    while name in taken or (OUT_DIR / f"{name}.txt").exists():
        name, n = f"site_{slug}_{n}", n + 1
    taken.add(name)
    return OUT_DIR / f"{name}.txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count, write nothing")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if any(OUT_DIR.glob("site_*.txt")) and not args.dry_run:
        sys.exit(f"{OUT_DIR} already has site_*.txt files: move them to _trash/ first.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SITE_CRAWL / "manifest.json").read_text(encoding="utf-8"))
    old_urls, seen_hashes, kept_shingles = existing_pages()
    counts, pages, skipped, taken = Counter(), [], [], set()

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
        sh = shingles(text) if reason is None else None
        if reason is None and near_duplicate(sh, kept_shingles):
            reason = "nearly the same text as another page"
        if reason:
            counts[reason] += 1
            skipped.append((title, reason))
            continue
        seen_hashes.add(body_hash(text))
        kept_shingles.append(sh)
        counts["imported"] += 1
        pages.append({"url": url, "title": title, "text": text, "fetched": entry["fetched"]})

    strip_site_names(pages)
    if not args.dry_run:
        for page in pages:
            path = unique_path(crawl.slugify(page["url"]), taken)
            header = (f"SOURCE_URL: {page['url']}\nTITLE: {page['title']}\nFETCHED: {page['fetched']}\n"
                      f"CRAWL: {CRAWL_LABEL}\n---\n")
            path.write_text(header + page["text"].strip() + "\n", encoding="utf-8")
    imported = [p["title"] for p in pages]

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
