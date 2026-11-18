"""Checks that every built page carries what Runbook 8 requires of it.

Each page in dist/sitemap.json needs a <title>, the demo banner, the noindex
meta, the footer credit, the VNIT Assistant script and exactly one <h1>;
content pages also need a Source line. No page may load a script, style, image
or frame from another domain. Exits with 1 on any problem.
"""
import json
import re
import sys
from pathlib import Path

DIST = Path(__file__).resolve().parent.parent / "dist"
CONTENT = Path(__file__).resolve().parent.parent / "content"

REQUIRED = {
    "demo banner": "Student project demo (VNIT Assistant). This is not the official VNIT website. Official site:",
    "banner link": '<a href="https://vnit.ac.in"',
    "noindex": '<meta name="robots" content="noindex, nofollow">',
    "footer credit": "Final-year project by Avinav, Nikhil, Shivanand and Vaibhav. Content copied from vnit.ac.in on the dates shown.",
    "assistant script": "assets/js/vnit-assistant.js",
}
REMOTE_LOAD = re.compile(r'<(script|img|iframe|link|source|video|audio)\b[^>]*\b(src|href)="(https?:)?//', re.I)


def problems(html, needs_source):
    found = []
    if not re.search(r"<title>[^<]+</title>", html):
        found.append("no <title>")
    for name, text in REQUIRED.items():
        if text not in html:
            found.append(f"no {name}")
    h1 = len(re.findall(r"<h1[\s>]", html))
    if h1 != 1:
        found.append(f"{h1} <h1> elements")
    if needs_source and not re.search(r'<p class="source">Source: <a href="https?://vnit\.ac\.in', html):
        found.append("no Source line")
    for m in REMOTE_LOAD.finditer(html):
        found.append(f"loads from another domain: {m.group(0)[:80]}")
    return found


def main():
    sitemap = json.loads((DIST / "sitemap.json").read_text(encoding="utf-8"))
    site_paths = {p["path"] for p in json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))}
    content_pages = {e["path"] for e in sitemap if e.get("source_path") in site_paths}
    bad = 0
    for entry in sitemap:
        html = (DIST / entry["path"]).read_text(encoding="utf-8")
        for problem in problems(html, entry["path"] in content_pages):
            print(f"{entry['path']}: {problem}")
            bad += 1
    extra = {str(p.relative_to(DIST)).replace("\\", "/") for p in DIST.rglob("*.html")} - {e["path"] for e in sitemap}
    for path in sorted(extra):
        print(f"{path}: built but not in sitemap.json")
        bad += 1
    print(f"{len(sitemap)} pages checked ({len(content_pages)} content pages), {bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
