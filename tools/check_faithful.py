"""The most important check: is every piece of text on the site copied from vnit.ac.in?

For every built page, takes the visible text of <main>, cut at block elements
(paragraphs, list items, table cells, headings) and at <br> and <span>, and
looks for each piece in the original HTML that vnit.ac.in sent for that page
(crawl/html/, from tools/crawl_site.py). Whitespace is ignored when comparing;
nothing else may differ. Menu labels and page titles come from the crawl too.
The home page and the notice list are checked against the chatbot's crawl and
notices.json, which they are built from. Labels the site adds itself are in
ALLOWED below.

Prints every piece that is not found; the target is zero. Exits with 1 otherwise.
Fix the build, not this check.
"""
import gzip
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DIST = HERE / "dist"
RAW = HERE.parent / "vnit-chatbot" / "data" / "raw"
CONTENT = HERE / "content"
CRAWL = HERE / "crawl"

# Labels, headings and buttons the site adds itself (not VNIT content).
ALLOWED = {
    "Home", "Skip to content", "Latest notices", "All notices", "News and events", "All news and events",
    "Quick links", "From the Director", "Read more", "Upcoming events", "Emergency contacts",
    "Admissions", "Academic calendar", "Ask the VNIT Assistant", "Fees", "Hostel", "Placements",
    "Scholarships", "Telephone directory", "Contact", "Notices", "Search notices", "News",
    "All", "Date", "Title", "Category", "Listed on:", "Page not found", "This page is not part of the demo site.",
    "Go to the home page", "VNIT Ranking", "Visvesvaraya National Institute of Technology, Nagpur",
    "Every document linked from vnit.ac.in that the VNIT Assistant has read, newest first. "
    "Each title opens the document itself on vnit.ac.in or Google Drive.",
    "No notice matches. Try fewer words, or ask the VNIT Assistant.",
    "academics", "admissions", "hostel", "other", "placements", "recruitment", "Undated",
}
PATTERNS = [
    re.compile(r"^Source: https?://\S+ \(fetched \d{4}-\d{2}-\d{2}\)$"),
    re.compile(r"^\d+ notices$"),
    re.compile(r"^\d+ news posts from vnit\.ac\.in, newest first\.$"),
    re.compile(r"^\d{4}(-\d{2}-\d{2})?$"),
    re.compile(r"^This page on vnit\.ac\.in is made of \d+ pictures?, which this demo does not copy\. "
               r"See them on vnit\.ac\.in\.$"),
    re.compile(r"^Listed on:"),
]
BREAKS = {"p", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "div", "br", "span", "section", "ul", "ol",
          "tr", "nav", "aside", "article", "button", "label", "input", "table", "dt", "dd", "blockquote"}


class MainText(HTMLParser):
    """Visible text inside <main>, as pieces cut at block elements."""

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


class AllText(HTMLParser):
    """Every text node of an original page (not scripts or styles), plus counter values."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        value = dict(attrs).get("data-to-value")
        if value:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def squash(text):
    return re.sub(r"[\s​ ]+", "", text)


def original_text(entry):
    parser = AllText()
    parser.feed(gzip.decompress((CRAWL / "html" / entry["file"]).read_bytes()).decode("utf-8", "replace"))
    return " ".join(parser.parts)


def raw_body(name):
    return (RAW / name).read_text(encoding="utf-8").partition("\n---\n")[2]


def menu_labels(items):
    for item in items:
        yield item["label"]
        yield from menu_labels(item["children"])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    site = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))
    menus = json.loads((CONTENT / "menus.json").read_text(encoding="utf-8"))
    notices = json.loads((CONTENT / "notices.json").read_text(encoding="utf-8"))
    manifest = json.loads((CRAWL / "manifest.json").read_text(encoding="utf-8"))
    sitemap = json.loads((DIST / "sitemap.json").read_text(encoding="utf-8"))
    by_path = {p["path"]: p for p in site}

    shared = [p["title"] for p in site] + [l for m in menus.values() for l in menu_labels(m)]
    home_sources = [raw_body(f) for f in ("home.txt", "history.txt", "director.txt")] + [n["title"] for n in notices]

    total_pieces = total_missing = 0
    for entry in sitemap:
        page = by_path.get(entry["source_path"])
        if page:
            sources = [original_text(manifest[page["source_url"]])]
        elif entry["source_path"] == "/":
            sources = home_sources
        else:
            sources = [n["title"] for n in notices]
        haystack = "\n".join(squash(s) for s in sources + shared)
        parser = MainText()
        parser.feed((DIST / entry["path"]).read_text(encoding="utf-8"))
        pieces = parser.text()
        total_pieces += len(pieces)
        for piece in pieces:
            if piece in ALLOWED or any(p.match(piece) for p in PATTERNS):
                continue
            if squash(piece) not in haystack:
                total_missing += 1
                print(f"{entry['path']}: NOT IN CRAWL: {piece[:160]}")
    print(f"{len(sitemap)} pages, {total_pieces} pieces of text checked, {total_missing} not found in the crawl")
    return 1 if total_missing else 0


if __name__ == "__main__":
    sys.exit(main())
