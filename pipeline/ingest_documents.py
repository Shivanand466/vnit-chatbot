"""
Bring VNIT's documents (notices, fee sheets, calendars, rule books...) into
the chatbot. Most of them are PDFs on Google Drive, linked from vnit.ac.in
pages; a few are PDFs on vnit.ac.in itself.

Run with the separate PDF environment (it has Docling installed):
    C:\\Users\\<you>\\.venvs\\vnit-pdf\\Scripts\\python.exe ingest_documents.py discover
    C:\\Users\\<you>\\.venvs\\vnit-pdf\\Scripts\\python.exe ingest_documents.py convert --limit 50

  discover  scan the crawled pages for document links, record title/date/type
            in data/documents/inventory.json
  convert   download + convert documents in priority order into
            data/raw/doc_<id>.txt. Safe to stop and re-run: finished
            documents are skipped.

What is deliberately NOT ingested (see select()):
  - lists of people: seating plans, merit/shortlist/selection lists, mess
    allotments, attendance, results. They're personal data, and useless
    for answering questions.
  - tenders/quotations, recruitment candidate lists, Hindi-only documents,
    images and videos.
"""
import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import drive_utils as du
from fetch_utils import USER_AGENT, is_allowed

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
DOC_DIR = ROOT / "data" / "documents"
INVENTORY = DOC_DIR / "inventory.json"
STATUS = DOC_DIR / "status.json"
IN_PROGRESS = DOC_DIR / "in_progress.txt"
DOC_TIMEOUT_SECONDS = 900
CACHE_DIR = Path.home() / ".cache" / "vnit-chatbot" / "pdfs"   # outside OneDrive: ~1GB of PDFs

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PAGES = 25
MIN_WORDS = 30

EXTRA_PAGES = [
    "https://vnit.ac.in/section/hostel/rules-regulations/",
    "https://vnit.ac.in/section/hostel/fees/",
    "https://vnit.ac.in/section/hostel/hostels/",
    "https://vnit.ac.in/section/hostel/mess/",
]

PEOPLE_LISTS = (r"seating|merit list|shortlist|selected candidates|selection list|provisional list|"
                r"allotment|result|attendance|roll ?no|list of (students|candidates)|interview|"
                r"eligible|not verified|unverified|waiting list|vacant seats|rejected|"
                r"constitution of|class committee")
BLANK_FORMS = r"\bform\b|\bformat\b"
# Content check after conversion -- titles alone miss lists (e.g. "Constitution of
# First Year Class Committees" held student names, roll numbers and phone numbers).
STUDENT_ROLL = re.compile(r"\b(BT|MT|BA|MS|PH|MB|DT|PD)\s?\d{2}\s?[A-Z]{2,5}\s?[0-9O]{2,4}\b", re.I)
STUDENT_EMAIL = re.compile(r"@students\.vnit\.ac\.in", re.I)
LONG_ID = re.compile(r"\b\d{10,15}\b")


def looks_like_personal_data(text: str) -> bool:
    """A list of students, judged by density rather than a raw count: the
    Academic Rule Book quotes 3 example roll numbers in ~7,500 words and must
    stay in; a class-committee list has 16 roll numbers in ~300 words."""
    words = max(1, len(text.split()))

    def dense(pattern, min_count=2, per_100_words=0.5):
        n = len(pattern.findall(text))
        return n >= min_count and n * 100 / words >= per_100_words

    return dense(STUDENT_ROLL) or dense(STUDENT_EMAIL) or len(LONG_ID.findall(text)) >= 25
PROCUREMENT = r"tender|quotation|corrigendum|\bbid\b|purchase|rate contract|gem ?bid|e-?procurement"
SKIP_PAGES = r"/section/stores|faculty-recruitment-2025-shortlisted|/recruitmen\b|/recruitment-rules"
DEVANAGARI = re.compile(r"[\u0900-\u097F]")

TIER0_PAGES = r"/section/academics/fees|academic-event-calendar|/section/academics/?$|/section/tnp|/section/hostel|/ciwg"
TIER0_WORDS = (r"fee|rule ?book|calendar|holiday|scholarship|hostel|mess|placement|brochure|"
               r"code of conduct|ragging|admission (procedure|reporting)|reporting instruction|"
               r"steps to be followed|remission|telephone directory|anti-ragging")


def _page_urls():
    urls = []
    for p in sorted(RAW_DIR.glob("*.txt")):
        if p.name.startswith("doc_"):
            continue
        m = re.search(r"^SOURCE_URL:\s*(\S+)", p.read_text(encoding="utf-8"), re.M)
        if m:
            urls.append(m.group(1))
    return urls + [u for u in EXTRA_PAGES if u not in urls]


def discover():
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    found = {}
    pages = _page_urls()
    for i, url in enumerate(pages, 1):
        if not is_allowed(url):
            continue
        time.sleep(1.0)
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [page error] {url}: {e}")
            continue
        for a in BeautifulSoup(resp.text, "html.parser").find_all("a", href=True):
            link = urljoin(url, a["href"].split("#")[0])
            text = a.get_text(" ", strip=True)[:200]
            fid = du.drive_file_id(link)
            if fid:
                key, entry = f"drive:{fid}", {"kind": "drive", "id": fid,
                                              "url": f"https://drive.google.com/file/d/{fid}/view"}
            elif urlparse(link).netloc == "vnit.ac.in" and urlparse(link).path.lower().endswith(".pdf"):
                key, entry = f"web:{link}", {"kind": "web", "url": link}
            else:
                continue
            if key not in found:
                found[key] = {**entry, "link_text": text, "found_on": url}
        print(f"[{i}/{len(pages)}] {len(found)} documents so far")

    key = du.load_key()
    for n, (k, v) in enumerate(found.items(), 1):
        if v["kind"] == "drive":
            try:
                v.update(du.file_metadata(v["id"], key))
            except du.DriveError as e:
                v["error"] = str(e)
        else:
            m = re.search(r"/uploads/(\d{4})/(\d{2})/", v["url"])
            v.update({"mimeType": "application/pdf", "name": Path(urlparse(v["url"]).path).name,
                      "modifiedTime": f"{m.group(1)}-{m.group(2)}-01" if m else ""})
        if n % 50 == 0:
            print(f"  metadata {n}/{len(found)}")
    INVENTORY.write_text(json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(found)} documents recorded in {INVENTORY}")


def title_of(v) -> str:
    text = v.get("link_text", "").strip()
    if not text or text.lower().startswith("http") or len(text) < 4:
        text = re.sub(r"\.pdf$", "", v.get("name", ""), flags=re.I)
        text = re.sub(r"[_]+", " ", text).strip()
    return text[:150] or v["url"]


def select(inventory: dict):
    """Return [(tier, key, entry)] of documents worth ingesting, most important first."""
    chosen = []
    for k, v in inventory.items():
        title = title_of(v)
        hay = f"{title} {v.get('name', '')}"
        if v.get("error") or v.get("mimeType") != "application/pdf":
            continue
        if int(v.get("size") or 0) > MAX_PDF_BYTES:
            continue
        if re.search(PEOPLE_LISTS, hay, re.I) or re.search(PROCUREMENT, hay, re.I):
            continue
        if re.search(BLANK_FORMS, title, re.I) and not re.search(r"fee", title, re.I):
            continue
        if re.search(SKIP_PAGES, v["found_on"]) or DEVANAGARI.search(title):
            continue
        year = (v.get("modifiedTime") or "0000")[:4]
        if re.search(TIER0_PAGES, v["found_on"]) or re.search(TIER0_WORDS, hay, re.I):
            tier = 0
        elif re.search(r"/section/academics/(notice|admission)", v["found_on"]) and year >= "2026":
            tier = 1
        else:
            tier = 2
        chosen.append((tier, k, v))
    # most important tier first; newest first within a tier
    chosen.sort(key=lambda t: (t[0], -int(re.sub(r"\D", "", (t[2].get("modifiedTime") or "0")[:10]) or 0)))
    return chosen


def out_path(key: str, v: dict) -> Path:
    ident = v["id"] if v["kind"] == "drive" else re.sub(r"[^A-Za-z0-9]+", "_", urlparse(v["url"]).path)[-60:]
    return RAW_DIR / f"doc_{ident}.txt"


def cache_path(v: dict) -> Path:
    return CACHE_DIR / (re.sub(r"[^A-Za-z0-9]+", "_", v.get("id") or v["url"])[-100:] + ".pdf")


def fetch_pdf(v: dict, key: str) -> Path:
    """Download (or reuse the cached copy of) a document; return its local path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = cache_path(v)
    if cache.exists():
        return cache
    if v["kind"] == "drive":
        data = du.download(v["id"], key)
    else:
        if not is_allowed(v["url"]):
            raise PermissionError("robots.txt disallows this file")
        time.sleep(1.0)
        r = requests.get(v["url"], headers={"User-Agent": USER_AGENT}, timeout=60)
        r.raise_for_status()
        data = r.content
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF")
    cache.write_bytes(data)
    return cache


def convert(limit: int, tiers):
    import doc_convert

    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    key = du.load_key()
    todo = [(t, k, v) for t, k, v in select(inventory) if t in tiers]
    done_now = 0
    print(f"{len(todo)} documents selected in tiers {sorted(tiers)}; "
          f"{sum(1 for _, k, _ in todo if k in status)} already processed.")

    for tier, k, v in todo:
        if done_now >= limit:
            break
        if k in status:
            continue
        title = title_of(v)
        t0 = time.time()
        IN_PROGRESS.write_text(k, encoding="utf-8")
        try:
            pdf = fetch_pdf(v, key)
            _, text = doc_convert.pdf_to_text(pdf, max_pages=MAX_PAGES)
        except Exception as e:
            status[k] = {"result": "error", "error": f"{type(e).__name__}: {e}"[:300], "title": title}
            print(f"  [error] {title[:70]}: {status[k]['error'][:120]}")
        else:
            words = len(text.split())
            devanagari_share = len(DEVANAGARI.findall(text)) / max(1, len(text))
            if words < MIN_WORDS:
                status[k] = {"result": "empty", "words": words, "title": title}
                print(f"  [empty] {title[:70]} ({words} words)")
            elif devanagari_share > 0.3:
                status[k] = {"result": "hindi", "title": title}
                print(f"  [hindi] {title[:70]}")
            elif looks_like_personal_data(text):
                status[k] = {"result": "personal_data", "title": title}
                print(f"  [skip: personal data] {title[:70]}")
            else:
                doc_date = (v.get("modifiedTime") or "")[:10] or date.today().isoformat()
                header = (f"SOURCE_URL: {v['url']}\nTITLE: {title}\nFETCHED: {doc_date}\n"
                          f"FOUND_ON: {v['found_on']}\n---\n")
                body = f"Document: {title} (dated {doc_date})\n{text.strip()}\n"
                out = out_path(k, v)
                out.write_text(header + body, encoding="utf-8")
                status[k] = {"result": "ok", "words": words, "file": out.name, "title": title,
                             "tier": tier, "seconds": round(time.time() - t0)}
                print(f"  [ok t{tier}] {title[:70]} ({words} words, {time.time()-t0:.0f}s)")
        done_now += 1
        STATUS.write_text(json.dumps(status, indent=1, ensure_ascii=False), encoding="utf-8")
        IN_PROGRESS.unlink(missing_ok=True)
        sys.stdout.flush()

    ok = sum(1 for s in status.values() if s["result"] == "ok")
    print(f"\nProcessed this run: {done_now}. Total ingested so far: {ok}.")


def supervise(limit: int, tiers):
    """Run convert() in a worker process and restart it if it dies.

    Docling's native OCR/layout code can crash the whole Python process
    (a real segmentation fault happened on one VNIT PDF) or hang. The worker
    records which document it is on in IN_PROGRESS; if the worker dies or
    that file goes stale, the document is marked failed and a fresh worker
    carries on with the rest.
    """
    import subprocess

    tier_arg = ",".join(str(t) for t in sorted(tiers))
    while True:
        IN_PROGRESS.unlink(missing_ok=True)
        worker = subprocess.Popen([sys.executable, "-u", __file__, "convert", "--worker",
                                   "--tiers", tier_arg, "--limit", str(limit)])
        timed_out = False
        while worker.poll() is None:
            time.sleep(5)
            if IN_PROGRESS.exists() and time.time() - IN_PROGRESS.stat().st_mtime > DOC_TIMEOUT_SECONDS:
                worker.kill()
                worker.wait()
                timed_out = True
        if not IN_PROGRESS.exists():
            return  # worker finished its list normally
        stuck = IN_PROGRESS.read_text(encoding="utf-8").strip()
        status = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        reason = "timeout" if timed_out else f"crashed (exit code {worker.returncode})"
        status[stuck] = {"result": "error", "error": reason, "title": title_of(inventory.get(stuck, {"url": stuck}))}
        STATUS.write_text(json.dumps(status, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  [error] {status[stuck]['title'][:70]}: worker {reason}; restarting on the remaining documents")
        sys.stdout.flush()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["discover", "convert", "plan"])
    ap.add_argument("--limit", type=int, default=10_000)
    ap.add_argument("--tiers", default="0,1,2")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    tiers = {int(t) for t in a.tiers.split(",")}
    if a.action == "discover":
        discover()
    elif a.action == "plan":
        sel = [s for s in select(json.loads(INVENTORY.read_text(encoding="utf-8"))) if s[0] in tiers]
        for t in sorted(tiers):
            items = [s for s in sel if s[0] == t]
            print(f"\n=== tier {t}: {len(items)} documents")
            for _, _, v in items[:25]:
                print(f"   {(v.get('modifiedTime') or '')[:10]}  {title_of(v)[:100]}")
    elif a.worker:
        convert(a.limit, tiers)
    else:
        supervise(a.limit, tiers)
