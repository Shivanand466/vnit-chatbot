"""The most important check: is every piece of text on the site copied from the crawl?

For every built page, takes the visible text of <main>, cut at block elements
(paragraphs, list items, table cells, headings) and at <br> and <span>, and
looks for each piece in the page's own raw file(s). Whitespace is ignored when
comparing, because the build may rejoin a sentence the crawl broke over two
lines; nothing else may differ. Notice rows are looked up in notices.json, and
labels the site adds itself (headings, buttons) are in ALLOWED below.

Prints every piece that is not found; the target is zero. Exits with 1 otherwise.
Fix the build, not this check.
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DIST = HERE / "dist"
RAW = HERE.parent / "vnit-chatbot" / "data" / "raw"
CONTENT = HERE / "content"

# Labels, headings and buttons the site adds itself (not VNIT content).
ALLOWED = {
    "Home", "Skip to content", "Latest notices", "All notices", "News and events", "All news and events",
    "Quick links", "From the Director", "Read more", "Upcoming events", "Emergency contacts",
    "Admissions", "Academic calendar", "Ask the VNIT Assistant", "Fees", "Hostel", "Placements",
    "Scholarships", "Telephone directory", "Contact", "Programmes offered", "Notices", "Search notices",
    "All", "Date", "Title", "Category", "Listed on:", "Page not found", "This page is not part of the demo site.",
    "Go to the home page", "VNIT Ranking",
    "Every document linked from vnit.ac.in that the VNIT Assistant has read, newest first. "
    "Each title opens the document itself on vnit.ac.in or Google Drive.",
    "No notice matches. Try fewer words, or ask the VNIT Assistant.",
    "academics", "admissions", "hostel", "other", "placements", "recruitment",
}
sys.path.insert(0, str(HERE / "tools"))
from inventory import SECTIONS  # noqa: E402
ALLOWED |= set(SECTIONS.values()) | {"All " + v.lower() for v in SECTIONS.values()}
SOURCE_LINE = re.compile(r"^Source: https?://\S+ \(fetched \d{4}-\d{2}-\d{2}\)$")
NOTICE_COUNT = re.compile(r"^\d+ notices$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BREAKS = {"p", "li", "td", "th", "h1", "h2", "h3", "div", "br", "span", "section", "ul", "ol", "tr",
          "nav", "aside", "article", "button", "label", "input", "table"}


class MainText(HTMLParser):
    """Collects the visible text inside <main>, as pieces cut at block elements."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.pieces = [""]
        self.links = []

    def cut(self):
        if self.pieces[-1].strip():
            self.pieces.append("")

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if tag == "main":
            self.depth += 1
        elif self.depth and (tag in BREAKS or "button" in classes):
            self.cut()
        if tag == "a":
            self.links.append("button" in classes)

    def handle_endtag(self, tag):
        if tag == "main":
            self.depth -= 1
        elif self.depth and (tag in BREAKS or (tag == "a" and self.links and self.links.pop())):
            self.cut()

    def handle_data(self, data):
        if self.depth:
            self.pieces[-1] += data

    def text(self):
        return [re.sub(r"\s+", " ", p).strip() for p in self.pieces if p.strip()]


def squash(text):
    """Text with every kind of whitespace (and zero-width spaces) removed."""
    return re.sub(r"[\s​ ]+", "", text)


def raw_body(raw_file):
    return (RAW / raw_file).read_text(encoding="utf-8").partition("\n---\n")[2]


def raw_header(raw_file):
    return (RAW / raw_file).read_text(encoding="utf-8").partition("\n---\n")[0]


def sources_for(path, pages, notices):
    """The squashed texts a page's pieces may come from."""
    by_slug = {p["slug"] + ".html": p for p in pages}
    titles = [p["title"] for p in pages]
    notice_text = [n["title"] for n in notices]
    if path in by_slug:
        page = by_slug[path]
        texts = [raw_body(page["raw_file"])]
        if path == "more/contact.html":
            texts.append(raw_body("telephone_directory.txt"))
        return texts + titles
    section = path.split("/")[0]
    if path.endswith("index.html") and path != "index.html":
        return [raw_body(p["raw_file"]) for p in pages if p["section"] == section] + titles
    if path == "index.html":
        news = [raw_body(p["raw_file"]) + raw_header(p["raw_file"]) for p in pages if p["section"] == "news"]
        return [raw_body("home.txt"), raw_body("history.txt"), raw_body("director.txt")] + news + notice_text
    if path == "notices.html":
        return notice_text + titles
    return titles


def unfound(pieces, sources):
    haystack = "\n".join(squash(s) for s in sources)
    missing = []
    for piece in pieces:
        if piece in ALLOWED or SOURCE_LINE.match(piece) or NOTICE_COUNT.match(piece) or DATE.match(piece):
            continue
        if piece.startswith("Listed on:") or piece in {"Visvesvaraya National Institute of Technology, Nagpur"}:
            continue
        if squash(piece) not in haystack:
            missing.append(piece)
    return missing


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pages = json.loads((CONTENT / "pages.json").read_text(encoding="utf-8"))
    notices = json.loads((CONTENT / "notices.json").read_text(encoding="utf-8"))
    sitemap = json.loads((DIST / "sitemap.json").read_text(encoding="utf-8"))
    total_pieces, total_missing = 0, 0
    for entry in sitemap:
        parser = MainText()
        parser.feed((DIST / entry["path"]).read_text(encoding="utf-8"))
        pieces = parser.text()
        missing = unfound(pieces, sources_for(entry["path"], pages, notices))
        total_pieces += len(pieces)
        total_missing += len(missing)
        for piece in missing:
            print(f"{entry['path']}: NOT IN CRAWL: {piece[:160]}")
    print(f"{len(sitemap)} pages, {total_pieces} pieces of text checked, {total_missing} not found in the crawl")
    return 1 if total_missing else 0


if __name__ == "__main__":
    sys.exit(main())
