"""Builds the notice list from the documents the chatbot already converted.

Reads vnit-chatbot/data/documents/inventory.json (every document link found on
vnit.ac.in) and status.json (what happened when each was converted), and
writes content/notices.json: one entry per document that was converted and
not excluded, newest first. Documents the chatbot left out as personal data,
or that failed to convert, never appear on the site.
"""
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOCS = HERE.parent / "vnit-chatbot" / "data" / "documents"
RAW = HERE.parent / "vnit-chatbot" / "data" / "raw"
OUT = HERE / "content" / "notices.json"

PRIVATE_PAGES = ("faculty-recruitment-2025-shortlisted-candidates",)

CATEGORIES = [
    ("hostel", "/section/hostel"),
    ("admissions", "/section/academics/admission"),
    ("academics", "/section/academics"),
    ("academics", "/academic-event-calendar"),
    ("recruitment", "recruit"),
    ("placements", "/section/tnp"),
]


def category(found_on):
    for name, part in CATEGORIES:
        if part in found_on:
            return name
    return "other"


def tidy(text):
    """Whitespace, plus the "Next post:" navigation words some link texts picked up."""
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    return re.sub(r"^(Next Next post|Previous Previous post): ", "", text)


def looks_like_file_name(text):
    return not text or text.lower().endswith((".pdf", ".docx", ".xlsx")) or " " not in text


def fetched_date(doc_file):
    for line in (RAW / doc_file).read_text(encoding="utf-8").splitlines()[:5]:
        if line.startswith("FETCHED:"):
            return line.split(":", 1)[1].strip()
    return ""


def build():
    inventory = json.loads((DOCS / "inventory.json").read_text(encoding="utf-8"))
    status = json.loads((DOCS / "status.json").read_text(encoding="utf-8"))
    notices = []
    for key, state in status.items():
        if state.get("result") != "ok" or not (RAW / state["file"]).exists():
            continue
        doc = inventory[key]
        if any(p in doc["found_on"] for p in PRIVATE_PAGES):
            continue
        link_text = tidy(doc.get("link_text", ""))
        title = tidy(state.get("title", ""))
        if looks_like_file_name(title) and link_text and not looks_like_file_name(link_text):
            title = link_text
        title = title or link_text
        notices.append({
            "title": title,
            "date": (doc.get("modifiedTime") or "")[:10] or fetched_date(state["file"]),
            "url": doc["url"],
            "found_on": doc["found_on"],
            "category": category(doc["found_on"]),
            "key": key,
        })
    notices.sort(key=lambda n: (n["date"], n["title"]), reverse=True)
    return notices, status


def main():
    notices, status = build()
    excluded = {k for k, v in status.items() if v.get("result") != "ok"}
    assert not excluded & {n["key"] for n in notices}, "an excluded document is in the notice list"
    assert len({n["url"] for n in notices}) == len(notices), "a document is listed twice"
    for n in notices:
        del n["key"]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(notices, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = Counter(n["category"] for n in notices)
    print(f"{len(notices)} notices written ({len(excluded)} documents excluded or not converted)")
    for name, count in counts.most_common():
        print(f"  {name:12} {count}")
    print(f"  newest: {notices[0]['date']} {notices[0]['title']}")


if __name__ == "__main__":
    main()
