"""Builds the VNIT website (a student project demo) from the chatbot's crawl.

Everything on the site is copied from vnit-chatbot/data/raw/ (the pages and
documents crawled from vnit.ac.in) through content/pages.json and
content/notices.json, which tools/inventory.py and tools/notices.py write.
Run those two first after the crawl changes, then this script. The result is
dist/: plain HTML with relative links, so it works from the folder, from any
web server, and under /site/ on the chatbot server.

Standard library only, so it runs on the exam-hall laptop with no installs.
"""
import html
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "vnit-chatbot" / "data" / "raw"
DOCS = HERE.parent / "vnit-chatbot" / "data" / "documents"
CONTENT = HERE / "content"
TEMPLATES = HERE / "templates"
DIST = HERE / "dist"

sys.path.insert(0, str(HERE / "tools"))
from inventory import SECTIONS  # noqa: E402

BOILERPLATE_SHARE = 0.4
HINDI_NAME = "विश्वेश्वरय्या राष्ट्रीय प्रौद्योगिकी संस्थान"

# Lines that are controls or labels of the old site's widgets, not content.
WIDGET_LINES = {"Previous slide", "Next slide", "Read more →", "vnit_web", "View More", "​"}
# Animated counters ("Faculty 0") were crawled before they counted up; the 0 is wrong.
COUNTER_LINE = re.compile(r"^[A-Za-z][A-Za-z .()']{1,40} 0$")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w/.-])(?:\+91[- ]?)?(?:\(?0\d{2,4}\)?[- ]?\d{3}[- ]?\d{1,4}[- ]?\d{0,4}|[6-9]\d{9})(?![\w/-])")
PERSON = re.compile(r"^(Dr|Prof|Shri|Smt|Mr|Mrs|Ms)\b\.?")
JOIN_AFTER = ("st", "nd", "rd", "th", "in", "of", "the", "and", "from", "to", "by", "for", "on", "at", "with", "a", "an", "as", "under", "&")


# ---------------------------------------------------------------- reading

def read_raw(raw_file):
    """(header dict, body lines) of a crawled file."""
    text = (RAW / raw_file).read_text(encoding="utf-8")
    head, _, body = text.partition("\n---\n")
    header = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        header[key.strip()] = value.strip()
    return header, body.splitlines()


def tidy(line):
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()


def load_json(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def find_boilerplate(raw_files):
    """Lines found in BOILERPLATE_SHARE or more of the page files (menus, footers)."""
    counts = Counter()
    for raw_file in raw_files:
        counts.update({tidy(line) for line in read_raw(raw_file)[1] if tidy(line)})
    limit = BOILERPLATE_SHARE * len(raw_files)
    return {line for line, n in counts.items() if n >= limit}


# ---------------------------------------------------------------- cleaning

def is_widget(line):
    return line in WIDGET_LINES or bool(COUNTER_LINE.match(line))


def should_join(previous, line):
    """True when the crawl broke one sentence over two lines."""
    if not previous:
        return False
    if line[0].islower() or line[0] in ".,;:)]":
        return True
    if previous.count("(") > previous.count(")"):
        return True
    last_word = previous.rsplit(" ", 1)[-1].lower()
    return len(previous) > 40 and last_word in JOIN_AFTER


def join(previous, line):
    return previous + ("" if line[0] in ".,;:)]" else " ") + line


def clean_lines(lines, boilerplate):
    """Crawl lines -> page lines: boilerplate and widget text dropped, repeats
    collapsed, sentences broken over lines rejoined. Wording is never changed."""
    out, seen = [], set()
    for raw in lines:
        line = tidy(raw)
        if line.endswith(" vnit_web"):
            line = line[: -len(" vnit_web")]
        if not line or line in boilerplate or is_widget(line):
            continue
        if out and line == out[-1]:
            continue
        if len(line) >= 25 and line in seen:
            continue
        seen.add(line)
        if out and should_join(out[-1], line):
            out[-1] = join(out[-1], line)
        else:
            out.append(line)
    return out


# ---------------------------------------------------------------- HTML

def esc(text):
    return html.escape(text, quote=True)


def linkify(text):
    """Escapes text, turning emails and phone numbers into mailto:/tel: links."""
    parts, pos = [], 0
    matches = sorted(list(EMAIL.finditer(text)) + list(PHONE.finditer(text)), key=lambda m: m.start())
    for m in matches:
        if m.start() < pos:
            continue
        parts.append(esc(text[pos:m.start()]))
        value = m.group(0)
        if "@" in value:
            parts.append(f'<a href="mailto:{esc(value)}">{esc(value)}</a>')
        else:
            digits = re.sub(r"[^\d+]", "", value)
            if len(digits.lstrip("+")) < 10:
                parts.append(esc(value))
            else:
                parts.append(f'<a href="tel:{digits}">{esc(value)}</a>')
        pos = m.end()
    parts.append(esc(text[pos:]))
    return "".join(parts)


def external(url, text, css=""):
    cls = f' class="{css}"' if css else ""
    return f'<a{cls} href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>'


def is_heading(line, next_line):
    return (len(line) <= 60 and not re.search(r"[.,;:!?]$", line) and not EMAIL.search(line)
            and not re.search(r"\d{5,}", line) and next_line is not None and len(next_line) > 120)


def table_rows(lines, start):
    """Consecutive ' | ' lines with the same number of cells, from start."""
    width = lines[start].count(" | ")
    end = start
    while end < len(lines) and " | " in lines[end] and lines[end].count(" | ") == width:
        end += 1
    return end


def cells(line):
    """Splits a table line; Docling's 'Header: value — Header: value' cells become columns."""
    out = []
    for cell in line.split(" | "):
        out.extend(part.strip() for part in cell.split(" — "))
    return out


def render_table(rows):
    body = "\n".join("<tr>" + "".join(f"<td>{linkify(c)}</td>" for c in cells(r)) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><tbody>\n{body}\n</tbody></table></div>'


def render_line(line, links):
    url = links.get(line)
    if url:
        return external(url, line, "doc-link")
    return linkify(line)


def render_people(lines, links):
    """Name, role, email lines -> one list item per person."""
    groups = []
    for line in lines:
        if PERSON.match(line) or not groups:
            groups.append([line])
        else:
            groups[-1].append(line)
    items = []
    for group in groups:
        rest = "".join(f"<br>{render_line(x, links)}" for x in group[1:])
        items.append(f"<li><strong>{render_line(group[0], links)}</strong>{rest}</li>")
    return '<ul class="people">\n' + "\n".join(items) + "\n</ul>"


def to_html(lines, links=None, skip_first=None):
    """Page lines -> HTML: headings, tables, lists of short lines, paragraphs.
    links maps a line's exact text to the document it links to."""
    links = links or {}
    blocks, short = [], []

    def flush_short():
        if sum(bool(PERSON.match(s)) for s in short) >= 2:
            blocks.append(render_people(short, links))
        elif len(short) >= 3:
            items = "\n".join(f"<li>{render_line(s, links)}</li>" for s in short)
            blocks.append(f'<ul class="lines">\n{items}\n</ul>')
        else:
            blocks.extend(f"<p>{render_line(s, links)}</p>" for s in short)
        short.clear()

    i = 0
    if skip_first and lines and lines[0] == skip_first:
        i = 1
    while i < len(lines):
        line = lines[i]
        next_line = lines[i + 1] if i + 1 < len(lines) else None
        if " | " in line and next_line and " | " in next_line and table_rows(lines, i) - i >= 2:
            flush_short()
            end = table_rows(lines, i)
            blocks.append(render_table(lines[i:end]))
            i = end
            continue
        if is_heading(line, next_line) and line not in links:
            flush_short()
            blocks.append(f"<h2>{esc(line)}</h2>")
        elif len(line) <= 90:
            short.append(line)
        else:
            flush_short()
            blocks.append(f"<p>{render_line(line, links)}</p>")
        i += 1
    flush_short()
    return "\n".join(blocks)


# ---------------------------------------------------------------- site data

class Site:
    """Everything the page builders share: pages, notices, menu, footer."""

    def __init__(self):
        self.pages = load_json("pages.json")
        self.notices = load_json("notices.json")
        self.by_slug = {p["slug"]: p for p in self.pages}
        self.by_raw = {p["raw_file"]: p for p in self.pages}
        all_raw = [p["raw_file"] for p in self.pages] + ["home.txt", "notices.txt"]
        self.boilerplate = find_boilerplate(all_raw)
        self.doc_links = self.load_doc_links()
        self.base = Template((TEMPLATES / "base.html").read_text(encoding="utf-8"))
        self.has_logo = (HERE / "assets" / "img" / "logo.png").exists()
        self.built = []

    def load_doc_links(self):
        """{page url: {link text: document url}} for converted, non-excluded documents."""
        inventory = json.loads((DOCS / "inventory.json").read_text(encoding="utf-8"))
        status = json.loads((DOCS / "status.json").read_text(encoding="utf-8"))
        links = {}
        for key, doc in inventory.items():
            if status.get(key, {}).get("result") == "personal_data":
                continue
            if "shortlisted-candidates" in doc.get("found_on", ""):
                continue
            text = tidy(doc.get("link_text", ""))
            if text:
                links.setdefault(norm_url(doc["found_on"]), {}).setdefault(text, doc["url"])
        return links

    def links_for(self, source_url):
        return self.doc_links.get(norm_url(source_url), {})

    def lines(self, raw_file):
        return clean_lines(read_raw(raw_file)[1], self.boilerplate)

    def section_pages(self, section):
        return [p for p in self.pages if p["section"] == section]

    def href(self, slug, root):
        return f"{root}{slug}.html"

    def menu(self, root):
        items = []
        for key, title in SECTIONS.items():
            links = [f'<li><a href="{root}{key}/index.html">All {esc(title.lower())}</a></li>']
            links += [f'<li><a href="{self.href(p["slug"], root)}">{esc(p["title"])}</a></li>'
                      for p in self.section_pages(key)]
            items.append(
                f'      <li><button class="menu-button" type="button" aria-expanded="false">{esc(title)}</button>'
                f'<ul class="submenu">{"".join(links)}</ul></li>')
        items.append(f'      <li><a href="{root}notices.html">Notices</a></li>')
        return "\n".join(items)

    def emergency(self):
        for line in read_raw("home.txt")[1]:
            if line.startswith("Emergency Contact Numbers"):
                return linkify(tidy(line))
        return ""

    def footer(self):
        lines = [tidy(x) for x in read_raw("contact_us.txt")[1] if tidy(x)]
        address = lines[1:4]
        phone = next(x for x in lines if x.startswith("Contact No"))
        email = next(x for x in lines if "director_office@" in x)
        root = "$root"
        return (
            '    <div><h2>Postal Address of VNIT</h2>'
            + "".join(f"<p>{esc(x)}</p>" for x in address) + "</div>\n"
            '    <div><h2>Director Office</h2>'
            f"<p>{linkify(phone)}</p><p>{linkify(email)}</p></div>\n"
            '    <div><h2>On this site</h2>'
            f'<p><a href="{root}more/contact.html">Contact Us</a></p>'
            f'<p><a href="{root}more/telephone-directory.html">Telephone Directory</a></p>'
            f'<p><a href="{root}notices.html">Notices</a></p>'
            f'<p><button class="button secondary" type="button" data-open-assistant>Ask the VNIT Assistant</button></p></div>'
        )

    def write(self, path, title, main, section="", scripts="", root_override=None):
        root = root_override or "../" * path.count("/")
        logo = f'<img src="{root}assets/img/logo.png" alt="VNIT logo">' if self.has_logo else ""
        page = self.base.substitute(
            title=esc(title), root=root, section=section, emergency=self.emergency(),
            logo=logo, hindi_name=HINDI_NAME, menu=self.menu(root),
            main=main.replace("$root", root),
            footer=Template(self.footer()).safe_substitute(root=root),
            scripts=scripts.replace("$root", root))
        out = DIST / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        self.built.append({"path": path, "title": title, "section": section})


def norm_url(url):
    return url.rstrip("/").replace("http://", "https://").replace("/index.php/", "/")


def source_line(page):
    return (f'    <p class="source">Source: {external(page["source_url"], page["source_url"])} '
            f'(fetched {esc(page["fetched"])})</p>')


def breadcrumbs(items):
    """items: [(label, href or None)]."""
    out = []
    for label, href in items:
        if href:
            out.append(f'<li><a href="{href}">{esc(label)}</a></li>')
        else:
            out.append(f'<li aria-current="page">{esc(label)}</li>')
    return "".join(out)


def first_sentence(lines):
    for line in lines:
        if len(line) > 60:
            match = re.match(r"(.+?[.!?])(\s|$)", line)
            return (match.group(1) if match else line)[:220]
    return lines[0][:220] if lines else ""


# ---------------------------------------------------------------- pages

def build_content_page(site, page, summary="", extra=""):
    template = Template((TEMPLATES / "page.html").read_text(encoding="utf-8"))
    section = page["section"]
    root = "$root"
    side = "\n".join(
        f'      <li><a href="{root}{p["slug"]}.html"'
        + (' aria-current="page"' if p is page else "") + f'>{esc(p["title"])}</a></li>'
        for p in site.section_pages(section))
    lines = site.lines(page["raw_file"])
    main = template.substitute(
        breadcrumbs=breadcrumbs([("Home", f"{root}index.html"),
                                 (SECTIONS[section], f"{root}{section}/index.html"),
                                 (page["title"], None)]),
        section_title=esc(SECTIONS[section]), side_menu=side, heading=esc(page["title"]),
        summary=summary,
        body=to_html(lines, site.links_for(page["source_url"]), skip_first=page["title"]) + extra,
        source=source_line(page))
    site.write(page["slug"] + ".html", page["title"], main, section)


def build_section_index(site, section):
    template = Template((TEMPLATES / "section.html").read_text(encoding="utf-8"))
    cards = []
    for page in site.section_pages(section):
        slug = page["slug"].split("/", 1)[1]
        intro = first_sentence(site.lines(page["raw_file"]))
        cards.append(f'<li><h2><a href="{slug}.html">{esc(page["title"])}</a></h2><p>{esc(intro)}</p></li>')
    main = template.substitute(
        breadcrumbs=breadcrumbs([("Home", "$rootindex.html"), (SECTIONS[section], None)]),
        heading=esc(SECTIONS[section]), cards="\n".join(cards))
    site.write(f"{section}/index.html", SECTIONS[section], main, section)


def raw_between(raw_file, start, stop):
    """Tidied lines of a raw file strictly between the line `start` and the line `stop`."""
    lines = [tidy(x) for x in read_raw(raw_file)[1]]
    first = lines.index(start) + 1
    last = lines.index(stop, first) if stop else len(lines)
    return [x for x in lines[first:last] if x]


def news_links(site):
    """{headline: page} for headlines that have their own page or appear on a news listing."""
    links = {}
    for page in site.section_pages("news"):
        header, body = read_raw(page["raw_file"])
        links.setdefault(tidy(header["TITLE"]), page)
        for line in body:
            line = tidy(line)
            if line.endswith(" vnit_web"):
                line = line[: -len(" vnit_web")]
            links.setdefault(line, page)
    return links


def home_news(site, limit=12):
    links = news_links(site)
    items, seen = [], set()
    for line in raw_between("home.txt", "📢 Latest VNIT News", "All News"):
        if line in seen or "�" in line or re.search(r"candidates", line, re.I):
            continue
        seen.add(line)
        page = links.get(line)
        text = f'<a href="{page["slug"]}.html">{esc(line)}</a>' if page else esc(line)
        items.append(f"        <li>{text}</li>")
        if len(items) == limit:
            break
    return "\n".join(items)


def home_events():
    lines = raw_between("home.txt", "🎯 Upcoming VNIT Events", "All Events")
    events, seen = [], set()
    for i, line in enumerate(lines):
        if line.startswith("📅") or line in seen:
            continue
        seen.add(line)
        date = lines[i + 1] if i + 1 < len(lines) and lines[i + 1].startswith("📅") else ""
        meta = f'<span class="meta">{esc(date)}</span>' if date else ""
        events.append(f"        <li>{esc(line)}{meta}</li>")
    return "\n".join(events)


def home_notices(site, limit=10):
    items = []
    for n in site.notices[:limit]:
        items.append(
            f'        <li>{external(n["url"], n["title"])}'
            f'<span class="meta">{esc(n["date"])}<span class="tag">{esc(n["category"])}</span></span></li>')
    return "\n".join(items)


QUICK_LINKS = [
    ("Fees", "admissions/fees.html"),
    ("Hostel", "students/hostel.html"),
    ("Academic calendar", "academics/academic-calendar.html"),
    ("Placements", "placements/training-and-placement.html"),
    ("Scholarships", "notices.html?q=scholarship"),
    ("Telephone directory", "more/telephone-directory.html"),
    ("Contact", "more/contact.html"),
]


def home_director(site):
    lines = site.lines("director.txt")
    name, role, bio = lines[0], lines[1], lines[2]
    if bio.startswith("Brief Bio: "):
        bio = bio[len("Brief Bio: "):]
    bio = " ".join(re.split(r"(?<=[a-z)]\.) (?=[A-Z])", bio)[:2])
    return f"      <p><strong>{esc(name)}</strong><br>{esc(role)}</p>\n      <p>{esc(bio)}</p>"


def home_rankings():
    lines = raw_between("home.txt", "VNIT Ranking", None)
    return "\n".join(f"        <li>{esc(x)}</li>" for x in lines)


def home_emergency():
    line = next(tidy(x) for x in read_raw("home.txt")[1] if x.startswith("Emergency Contact Numbers"))
    return f"      <p>{linkify(line)}</p>"


def build_home(site):
    template = Template((TEMPLATES / "home.html").read_text(encoding="utf-8"))
    intro = re.match(r"(.+?\.)\s", site.lines("history.txt")[0]).group(1)
    quick = "\n".join(f'        <li><a href="{href}">{esc(label)}</a></li>' for label, href in QUICK_LINKS)
    main = template.substitute(
        intro=esc(intro), notices=home_notices(site), news=home_news(site), quick_links=quick,
        director=home_director(site), events=home_events(), rankings=home_rankings(),
        emergency=home_emergency())
    site.write("index.html", "Home", main, "home")


PROGRAMME = re.compile(r"^(B\.? ?Tech|M\.? ?Tech|Ph\.? ?D|B\.? ?Arch|M\.? ?Sc|M\.? ?Arch|MBA|M\. ?Plan)")


def department_summary(site, page):
    """A box of the programme lines and contacts found in the department's own file."""
    lines = site.lines(page["raw_file"])
    programmes = [x for x in lines if PROGRAMME.match(x) and len(x) <= 70
                  and not x.endswith(":") and not re.search(r"admission|scholar|presented", x, re.I)]
    programmes = [x for x in dict.fromkeys(programmes)
                  if not any(o != x and o.startswith(x.rstrip(".")) for o in programmes)]
    contacts = [x for x in lines if (EMAIL.search(x) or PHONE.search(x)) and len(x) <= 120]
    parts = []
    if programmes:
        parts.append("<h2>Programmes offered</h2><ul>"
                     + "".join(f"<li>{esc(x)}</li>" for x in dict.fromkeys(programmes)) + "</ul>")
    if contacts:
        parts.append("<h2>Contact</h2><ul>" + "".join(f"<li>{linkify(x)}</li>" for x in contacts[:4]) + "</ul>")
    if not parts:
        return ""
    return '    <div class="summary-box">' + "".join(parts) + "</div>\n"


def build_contact_page(site, page):
    """Contact Us, followed by the telephone directory page's text."""
    directory = site.by_slug["more/telephone-directory"]
    extra = (f'<h2>{esc(directory["title"])}</h2>\n'
             + to_html(site.lines(directory["raw_file"]), site.links_for(directory["source_url"]))
             + "\n" + source_line(directory).strip())
    build_content_page(site, page, extra=extra)


def build_notices(site):
    template = Template((TEMPLATES / "notices.html").read_text(encoding="utf-8"))
    found_on_titles = {norm_url(p["source_url"]): p for p in site.pages}
    found_on_titles[norm_url("https://vnit.ac.in")] = {"title": "Home", "slug": "index"}
    categories = Counter(n["category"] for n in site.notices)
    filters = ['    <button class="filter" type="button" data-category="all" aria-pressed="true">All</button>']
    filters += [f'    <button class="filter" type="button" data-category="{esc(c)}" aria-pressed="false">{esc(c)}</button>'
                for c, _ in categories.most_common()]
    rows = []
    for n in site.notices:
        page = found_on_titles.get(norm_url(n["found_on"]))
        where = (f'<span class="found-on">Listed on: <a href="{page["slug"]}.html">{esc(page["title"])}</a></span>'
                 if page else "")
        rows.append(f'<tr data-category="{esc(n["category"])}"><td>{esc(n["date"])}</td>'
                    f'<td>{external(n["url"], n["title"])}{where}</td><td>{esc(n["category"])}</td></tr>')
    main = template.substitute(filters="\n".join(filters), count=len(rows), rows="\n".join(rows))
    site.write("notices.html", "Notices", main, "notices",
               scripts='<script src="$rootassets/js/notices.js"></script>\n')


def build_404(site):
    main = ('<h1>Page not found</h1>\n'
            '<p>This page is not part of the demo site.</p>\n'
            '<p><a class="button" href="$rootindex.html">Go to the home page</a> '
            '<button class="button secondary" type="button" data-open-assistant>Ask the VNIT Assistant</button></p>')
    site.write("404.html", "Page not found", main, "404", root_override="/site/")


def copy_assets():
    target = DIST / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(HERE / "assets", target)


def report_boilerplate(site):
    if site.boilerplate:
        print(f"Dropped as boilerplate (in {BOILERPLATE_SHARE:.0%} or more of page files):")
        for line in sorted(site.boilerplate):
            print("  ", line)
    else:
        print(f"No line is in {BOILERPLATE_SHARE:.0%} or more of page files; nothing dropped as boilerplate.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    site = Site()
    DIST.mkdir(exist_ok=True)
    copy_assets()
    for page in site.pages:
        if page["slug"] == "more/contact":
            build_contact_page(site, page)
        elif page["section"] == "departments":
            build_content_page(site, page, summary=department_summary(site, page))
        else:
            build_content_page(site, page)
    for section in SECTIONS:
        build_section_index(site, section)
    build_home(site)
    build_notices(site)
    build_404(site)
    (DIST / "sitemap.json").write_text(json.dumps(site.built, indent=1, ensure_ascii=False), encoding="utf-8")
    report_boilerplate(site)
    print(f"Built {len(site.built)} pages into dist/")


if __name__ == "__main__":
    main()
