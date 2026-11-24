"""Checks that every link inside the built site leads to a file that exists.

Reads every href and src in dist/*.html. Links to other pages of the site must
resolve to a file in dist/ (a folder means its index.html); external links are
only counted per domain, never fetched. Exits with 1 if any internal link is broken.
"""
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

DIST = Path(__file__).resolve().parent.parent / "dist"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value is not None:
                self.links.append(value)


def target(page, link):
    """The dist/ file an internal link points at."""
    path = unquote(urlsplit(link).path)
    if path.startswith("/site/"):
        resolved = DIST / path[len("/site/"):]
    else:
        resolved = (page.parent / path).resolve()
    return resolved / "index.html" if resolved.is_dir() or path.endswith("/") else resolved


def main():
    broken, external, internal = [], Counter(), 0
    pages = sorted(DIST.rglob("*.html"))
    for page in pages:
        parser = LinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for link in parser.links:
            parts = urlsplit(link)
            if parts.scheme in ("http", "https"):
                external[parts.netloc] += 1
            elif parts.scheme in ("mailto", "tel"):
                external[parts.scheme + ":"] += 1
            elif not parts.path:
                continue
            else:
                internal += 1
                if not target(page, link).is_file():
                    broken.append(f"{page.relative_to(DIST)} -> {link}")
    print(f"{len(pages)} pages, {internal} internal links, {sum(external.values())} external links")
    for domain, count in external.most_common():
        print(f"  {count:6}  {domain}")
    for b in broken:
        print("BROKEN", b)
    print(f"{len(broken)} broken internal links")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
