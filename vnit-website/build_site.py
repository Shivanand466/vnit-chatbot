"""Builds the VNIT website (a student project demo): every crawled page of vnit.ac.in.

Reads what tools/extract.py made from the full crawl of vnit.ac.in
(content/site.json, content/menus.json, content/pages/*.html), plus the
chatbot's crawl for the home page and the notice list (content/notices.json,
from tools/notices.py), and writes dist/: one page per vnit.ac.in page, at the
same path (vnit.ac.in/engineering/cse/ becomes dist/engineering/cse/index.html),
with the real site's menus, a news archive, the notice list and the home page.
Every link inside the site is relative, so dist/ works from the folder, from any
web server, and under /site/ on the chatbot server.

Standard library only, so it runs on the exam-hall laptop with no installs.
"""
import html
import json
import re
import shutil
import sys
from pathlib import Path
from string import Template
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "vnit-chatbot" / "data" / "raw"
CONTENT = HERE / "content"
TEMPLATES = HERE / "templates"
DIST = HERE / "dist"

HINDI_NAME = "विश्वेश्वरय्या राष्ट्रीय प्रौद्योगिकी संस्थान"
NEWS_ARCHIVE = "/news-archive/"
NOTICES = "/notices/"

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w/.-])(?:\+91[- ]?)?(?:\(?0\d{2,4}\)?[- ]?\d{3}[- ]?\d{1,4}[- ]?\d{0,4}|[6-9]\d{9})(?![\w/-])")


# ---------------------------------------------------------------- small helpers

def esc(text):
    return html.escape(text, quote=True)


def tidy(line):
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()


def load_json(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def read_raw(raw_file):
    """(header dict, body lines) of a file in the chatbot's crawl."""
    text = (RAW / raw_file).read_text(encoding="utf-8")
    head, _, body = text.partition("\n---\n")
    header = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        header[key.strip()] = value.strip()
    return header, body.splitlines()


def linkify(text):
    """Escapes text, turning emails and phone numbers into mailto:/tel: links."""
    parts, pos = [], 0
    matches = sorted(list(EMAIL.finditer(text)) + list(PHONE.finditer(text)), key=lambda m: m.start())
    for m in matches:
        if m.start() < pos:
            continue
        parts.append(esc(text[pos:m.start()]))
        value = m.group(0)
        digits = re.sub(r"[^\d+]", "", value)
        if "@" in value:
            parts.append(f'<a href="mailto:{esc(value)}">{esc(value)}</a>')
        elif len(digits.lstrip("+")) >= 10:
            parts.append(f'<a href="tel:{digits}">{esc(value)}</a>')
        else:
            parts.append(esc(value))
        pos = m.end()
    parts.append(esc(text[pos:]))
    return "".join(parts)


def external(url, text, css=""):
    cls = f' class="{css}"' if css else ""
    return f'<a{cls} href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>'


def out_file(path):
    """dist/ file for a site path: /a/b/ -> a/b/index.html, / -> index.html, /404.html -> 404.html."""
    inner = path.strip("/")
    if inner.endswith(".html"):
        return inner
    return f"{inner}/index.html" if inner else "index.html"


def norm_url(url):
    url = re.sub(r"^http://", "https://", url.split("#")[0].split("?")[0])
    url = url.replace("://www.", "://").replace("/index.php/", "/")
    if not url.endswith("/") and "." not in url.rsplit("/", 1)[-1]:
        url += "/"
    return url


# ---------------------------------------------------------------- the site

class Site:
    """Everything the page builders share: pages, menus, links, the page frame."""

    def __init__(self):
        self.pages = load_json("site.json")
        self.menus = load_json("menus.json")
        self.notices = load_json("notices.json")
        self.by_path = {p["path"]: p for p in self.pages}
        self.subsite_titles = {s: self.by_path[s]["title"] for s in self.menus if s in self.by_path}
        self.base = Template((TEMPLATES / "base.html").read_text(encoding="utf-8"))
        self.has_logo = (HERE / "assets" / "img" / "logo.png").exists()
        self.built = []
        self.footer_cache = None

    def href(self, target, root):
        """(href on our site, opens elsewhere?) for a target from content or menus."""
        if target.startswith("vnit:"):
            path = target[len("vnit:"):]
            if re.match(r"/(index\.php/)?category/", path):
                return root + out_file(NEWS_ARCHIVE), False
            if path in self.by_path or path == "/":
                return root + out_file(path), False
            return "https://vnit.ac.in" + path, True
        if target.startswith(("http://", "https://")):
            n = norm_url(target)
            if n.startswith("https://vnit.ac.in/") and "/wp-content/" not in n:
                return self.href("vnit:" + n[len("https://vnit.ac.in"):], root)
            return target, True
        return target, False

    def link(self, target, text, root):
        if not target:
            return f'<span class="menu-label">{esc(text)}</span>'
        href, outside = self.href(target, root)
        extra = ' target="_blank" rel="noopener"' if outside else ""
        return f'<a href="{esc(href)}"{extra}>{esc(text)}</a>'

    # ------------------------------------------------ menus

    def menu_items(self, items, root):
        out = []
        for item in items:
            label = self.link(item["href"], item["label"], root)
            if item["children"]:
                out.append(f'<li class="has-children">{label}<ul>{self.menu_items(item["children"], root)}</ul></li>')
            else:
                out.append(f"<li>{label}</li>")
        return "".join(out)

    def main_menu(self, root):
        items = []
        for item in self.menus.get("/", []):
            if item["label"] == "Home":
                continue
            if item["children"]:
                top = f"<li>{self.link(item['href'], item['label'], root)}</li>" if item["href"] else ""
                items.append(
                    f'      <li><button class="menu-button" type="button" aria-expanded="false">{esc(item["label"])}</button>'
                    f'<ul class="submenu">{top}{self.menu_items(item["children"], root)}</ul></li>')
            else:
                items.append(f'      <li>{self.link(item["href"], item["label"], root)}</li>')
        items.append(f'      <li><a href="{root}{out_file(NEWS_ARCHIVE)}">News</a></li>')
        items.append(f'      <li><a href="{root}{out_file(NOTICES)}">Notices</a></li>')
        return "\n".join(items)

    def side_menu(self, page, root):
        """A sub-site's own menu (department, section) beside its pages."""
        sub = page.get("subsite", "/")
        if sub == "/" or not self.menus.get(sub):
            return ""
        title = self.subsite_titles.get(sub, "")
        home = f'<a href="{root}{out_file(sub)}">{esc(title)}</a>' if title else ""
        return (f'  <aside class="side-menu" aria-label="{esc(title or "Section")} menu">\n'
                f'    <h2 class="side-menu-title">{home}</h2>\n'
                f'    <ul>{self.menu_items(self.menus[sub], root)}</ul>\n  </aside>\n')

    # ------------------------------------------------ frame

    def emergency(self):
        for line in read_raw("home.txt")[1]:
            if line.startswith("Emergency Contact Numbers"):
                return linkify(tidy(line))
        return ""

    def footer(self):
        if self.footer_cache is None:
            lines = [tidy(x) for x in read_raw("contact_us.txt")[1] if tidy(x)]
            phone = next(x for x in lines if x.startswith("Contact No"))
            email = next(x for x in lines if "director_office@" in x)
            self.footer_cache = (
                '    <div><h2>Postal Address of VNIT</h2>' + "".join(f"<p>{esc(x)}</p>" for x in lines[1:4]) + "</div>\n"
                f'    <div><h2>Director Office</h2><p>{linkify(phone)}</p><p>{linkify(email)}</p></div>\n'
                '    <div><h2>On this site</h2>'
                '<p><a href="$rootcontact-us/index.html">Contact Us</a></p>'
                '<p><a href="$roottelephone-directory/index.html">Telephone Directory</a></p>'
                f'<p><a href="$root{out_file(NOTICES)}">Notices</a> · <a href="$root{out_file(NEWS_ARCHIVE)}">News</a></p>'
                '<p><button class="button secondary" type="button" data-open-assistant>Ask the VNIT Assistant</button></p></div>')
        return self.footer_cache

    def write(self, path, title, main, section="", scripts="", root_override=None):
        rel = out_file(path)
        root = root_override or "../" * rel.count("/")
        logo = f'<img src="{root}assets/img/logo.png" alt="VNIT logo">' if self.has_logo else ""
        page = self.base.substitute(
            title=esc(title), root=root, section=esc(section), emergency=self.emergency(),
            logo=logo, hindi_name=HINDI_NAME, menu=self.main_menu(root),
            main=main.replace("$root", root), footer=self.footer().replace("$root", root),
            scripts=scripts.replace("$root", root))
        # Links keep the address's %-encoding (as on vnit.ac.in); the file on disk uses the real
        # characters, which is what a browser or server looks for after decoding the link.
        out = DIST / unquote(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        self.built.append({"path": unquote(rel), "title": title, "section": section, "source_path": path})


# ---------------------------------------------------------------- content pages

def resolve_links(site, body, root):
    """Points vnit:/path/ links at our copies; links that leave the site open in a new tab."""
    def fix(m):
        href, outside = site.href(html.unescape(m.group(1)), root)
        extra = ' target="_blank" rel="noopener"' if outside else ""
        return f'<a href="{esc(href)}"{extra}>'
    return re.sub(r'<a href="([^"]*)">', fix, body)


def wrap_tables(body):
    return body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")


def breadcrumbs(items):
    out = [f'<li><a href="{href}">{esc(label)}</a></li>' if href else f'<li aria-current="page">{esc(label)}</li>'
           for label, href in items]
    return '<nav class="breadcrumbs" aria-label="Breadcrumb"><ol>' + "".join(out) + "</ol></nav>"


def source_line(page):
    return (f'<p class="source">Source: {external(page["source_url"], page["source_url"])} '
            f'(fetched {esc(page["fetched"])})</p>')


def pictures_note(page):
    if page["words"] > 0 or not page.get("images"):
        return ""
    n = page["images"]
    return (f'<p class="pictures-note">This page on vnit.ac.in is made of {n} picture{"s" if n != 1 else ""}, '
            f'which this demo does not copy. {external(page["source_url"], "See them on vnit.ac.in")}.</p>\n')


def menu_children(site, path):
    """The menu entries under this page, if some menu on vnit.ac.in lists it as a heading."""
    def walk(items):
        for item in items:
            if item["href"] == "vnit:" + path and item["children"]:
                return item["children"]
            found = walk(item["children"])
            if found:
                return found
        return None
    for items in site.menus.values():
        found = walk(items)
        if found:
            return found
    return None


def empty_note(site, page, root):
    """Pages that are empty on vnit.ac.in: list their menu entries, or say plainly that they are empty."""
    if page["words"] > 0 or page.get("images"):
        return ""
    children = menu_children(site, page["path"])
    if children:
        return f'<ul class="child-pages">{site.menu_items(children, root)}</ul>\n'
    return (f'<p class="pictures-note">This page on vnit.ac.in has no text of its own. '
            f'{external(page["source_url"], "See it on vnit.ac.in")}.</p>\n')


def build_page(site, page):
    rel = out_file(page["path"])
    root = "../" * rel.count("/")
    body = (CONTENT / "pages" / f"{page['slug']}.html").read_text(encoding="utf-8")
    body = wrap_tables(resolve_links(site, body, root))
    crumbs = [("Home", "$rootindex.html")]
    sub = page.get("subsite", "/")
    if sub not in ("/", page["path"]) and sub in site.subsite_titles:
        crumbs.append((site.subsite_titles[sub], "$root" + out_file(sub)))
    if page["kind"] == "post":
        crumbs.append(("News", "$root" + out_file(NEWS_ARCHIVE)))
    crumbs.append((page["title"], None))
    date = f'<p class="post-date">{esc(page["date"])}</p>\n' if page["kind"] == "post" and page["date"] else ""
    side = site.side_menu(page, "$root")
    article = (f'  <article class="content">\n    <h1>{esc(page["title"])}</h1>\n{date}{pictures_note(page)}{empty_note(site, page, "$root")}'
               f'{body}\n{source_line(page)}\n  </article>\n')
    layout = "page-layout" if side else "page-layout single"
    main = breadcrumbs(crumbs) + f'\n<div class="{layout}">\n{side}{article}</div>'
    site.write(page["path"], page["title"], main, section=sub.strip("/") or "main")


def build_news_archive(site):
    posts = sorted((p for p in site.pages if p["kind"] == "post"), key=lambda p: (p["date"], p["title"]), reverse=True)
    groups, rows = {}, []
    for p in posts:
        groups.setdefault(p["date"][:4] or "Undated", []).append(p)
    for year, items in groups.items():
        rows.append(f'<h2>{esc(year)}</h2>\n<ul class="item-list">')
        rows += [f'<li><a href="$root{out_file(p["path"])}">{esc(p["title"])}</a>'
                 f'<span class="meta">{esc(p["date"])}</span></li>' for p in items]
        rows.append("</ul>")
    main = (breadcrumbs([("Home", "$rootindex.html"), ("News", None)]) +
            f'\n<h1>News</h1>\n<p class="notice-count">{len(posts)} news posts from vnit.ac.in, newest first.</p>\n'
            + "\n".join(rows))
    site.write(NEWS_ARCHIVE, "News", main, "news")


# ---------------------------------------------------------------- home page (from the chatbot's crawl)

def raw_between(raw_file, start, stop):
    lines = [tidy(x) for x in read_raw(raw_file)[1]]
    first = lines.index(start) + 1
    last = lines.index(stop, first) if stop else len(lines)
    return [x for x in lines[first:last] if x]


def home_news(site, limit=12):
    titles = {tidy(p["title"]).rstrip("."): p for p in site.pages if p["kind"] == "post"}
    items, seen = [], set()
    for line in raw_between("home.txt", "📢 Latest VNIT News", "All News"):
        if line in seen or "�" in line or re.search(r"candidates", line, re.I):
            continue
        seen.add(line)
        page = titles.get(line.rstrip("."))
        text = f'<a href="{out_file(page["path"])}">{esc(line)}</a>' if page else esc(line)
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
    return "\n".join(
        f'        <li>{external(n["url"], n["title"])}'
        f'<span class="meta">{esc(n["date"])}<span class="tag">{esc(n["category"])}</span></span></li>'
        for n in site.notices[:limit])


QUICK_LINKS = [
    ("Fees", "section/academics/fees/index.html"),
    ("Hostel", "section/hostel/index.html"),
    ("Academic calendar", "academic-event-calendar/index.html"),
    ("Placements", "section/tnp/index.html"),
    ("Scholarships", "notices/index.html?q=scholarship"),
    ("Telephone directory", "telephone-directory/index.html"),
    ("Contact", "contact-us/index.html"),
]


def home_director():
    lines = [tidy(x) for x in read_raw("director.txt")[1] if tidy(x)]
    name, role = lines[0], lines[1]
    bio = " ".join(lines[3:5]).lstrip(": ")
    bio = " ".join(re.split(r"(?<=[a-z)]\.) (?=[A-Z])", bio)[:2])
    return f"      <p><strong>{esc(name)}</strong><br>{esc(role)}</p>\n      <p>{esc(bio)}</p>"


def home_rankings():
    return "\n".join(f"        <li>{esc(x)}</li>" for x in raw_between("home.txt", "VNIT Ranking", None))


def home_emergency():
    line = next(tidy(x) for x in read_raw("home.txt")[1] if x.startswith("Emergency Contact Numbers"))
    return f"      <p>{linkify(line)}</p>"


def build_home(site):
    template = Template((TEMPLATES / "home.html").read_text(encoding="utf-8"))
    history = " ".join(tidy(x) for x in read_raw("history.txt")[1])
    intro = re.match(r"(.+?\.)\s", history).group(1)
    quick = "\n".join(f'        <li><a href="{href}">{esc(label)}</a></li>' for label, href in QUICK_LINKS)
    main = template.substitute(
        intro=esc(intro), notices=home_notices(site), news=home_news(site), quick_links=quick,
        director=home_director(), events=home_events(), rankings=home_rankings(), emergency=home_emergency())
    site.write("/", "Home", main, "home")


# ---------------------------------------------------------------- notices, 404

def build_notices(site):
    template = Template((TEMPLATES / "notices.html").read_text(encoding="utf-8"))
    counts = {}
    for n in site.notices:
        counts[n["category"]] = counts.get(n["category"], 0) + 1
    filters = ['    <button class="filter" type="button" data-category="all" aria-pressed="true">All</button>']
    filters += [f'    <button class="filter" type="button" data-category="{esc(c)}" aria-pressed="false">{esc(c)}</button>'
                for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    rows = []
    for n in site.notices:
        path = norm_url(n["found_on"]).replace("https://vnit.ac.in", "")
        page = site.by_path.get(path)
        where = (f'<span class="found-on">Listed on: <a href="$root{out_file(path)}">{esc(page["title"])}</a></span>'
                 if page else "")
        rows.append(f'<tr data-category="{esc(n["category"])}"><td>{esc(n["date"])}</td>'
                    f'<td>{external(n["url"], n["title"])}{where}</td><td>{esc(n["category"])}</td></tr>')
    main = template.substitute(filters="\n".join(filters), count=len(rows), rows="\n".join(rows))
    site.write(NOTICES, "Notices", main, "notices", scripts='<script src="$rootassets/js/notices.js"></script>\n')


def build_404(site):
    main = ('<h1>Page not found</h1>\n<p>This page is not part of the demo site.</p>\n'
            '<p><a class="button" href="$rootindex.html">Go to the home page</a> '
            '<button class="button secondary" type="button" data-open-assistant>Ask the VNIT Assistant</button></p>')
    site.write("/404.html", "Page not found", main, "404", root_override="/site/")


def copy_assets():
    shutil.copytree(HERE / "assets", DIST / "assets")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    site = Site()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    copy_assets()
    for page in site.pages:
        if page["path"] != "/":
            build_page(site, page)
    build_news_archive(site)
    build_notices(site)
    build_home(site)
    build_404(site)
    (DIST / "sitemap.json").write_text(json.dumps(site.built, indent=1, ensure_ascii=False), encoding="utf-8")
    posts = sum(1 for p in site.pages if p["kind"] == "post")
    print(f"Built {len(site.built)} pages into dist/ ({posts} news posts, {len(site.menus)} menus)")


if __name__ == "__main__":
    main()
