"""Turns the crawled HTML of vnit.ac.in into clean page content and menus.

Reads crawl/manifest.json and crawl/html/ (written by tools/crawl_site.py) and
writes:
  content/site.json      one entry per page: path, title, date, sub-site, source
  content/menus.json     the main menu and each sub-site's own menu, as on vnit.ac.in
  content/pages/*.html   each page's own content as plain, safe HTML
  content/skipped.json   pages left out, and why

Only the page's own content is kept (headings, paragraphs, lists, tables,
links); the old site's header, footer, scripts, styles, images, forms and
sliders are dropped, and every attribute except links and table spans is
removed. Text is never changed. Links to other vnit.ac.in pages that were
crawled become "vnit:/path/" so build_site.py can point them at our copy.

Uses BeautifulSoup (installed with Anaconda, as the chatbot's crawler does);
build_site.py itself stays standard-library only.
"""
import gzip
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment, NavigableString

HERE = Path(__file__).resolve().parent.parent
CRAWL = HERE / "crawl"
CONTENT = HERE / "content"
PAGES = CONTENT / "pages"

KEEP = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "table", "thead", "tbody",
        "tfoot", "tr", "th", "td", "a", "strong", "b", "em", "i", "u", "br", "blockquote",
        "dl", "dt", "dd", "sup", "sub", "caption", "hr"}
DROP = {"script", "style", "noscript", "iframe", "img", "svg", "form", "input", "button", "select",
        "textarea", "video", "audio", "picture", "source", "canvas", "object", "embed", "map",
        "link", "meta", "template", "label", "nav"}
DROP_CLASSES = re.compile(
    r"elementor-hidden-desktop|swiper-slide-duplicate|elementor-tabs-wrapper|screen-reader-text|"
    r"elementor-swiper-button|swiper-pagination|elementor-share|sharedaddy|post-navigation|"
    r"elementor-widget-image(?!-box)|wp-block-image|elementor-widget-google_maps|elementor-widget-video")
BLOCKS = {"div", "section", "article", "header", "footer", "aside", "main", "figure", "figcaption",
          "center", "address"}

# Pages whose job is to list named individuals (candidates, selected students): left out (privacy).
PRIVATE_TITLE = re.compile(
    r"shortlist|selected (candidates|students)|list of (eligible|selected|candidates|provisionally)|"
    r"provisional (selection )?list|merit list|qualified|candidates (selected|allowed|qualified)|"
    r"score access|marks secured|result of|interview result|waiting list", re.I)

SITE_SUFFIX = re.compile(r"\s*[–—|-]\s*(VNIT Nagpur.*|Hostel Section|Research and Consultancy|"
                         r"VNIT Academic and Exam Section)\s*$")


def normalise(url):
    parts = urlsplit(url)
    path = re.sub(r"/+", "/", parts.path or "/")
    path = re.sub(r"^/index\.php/", "/", path)
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return urlunsplit(("https", "vnit.ac.in", path, "", ""))


def is_vnit(url):
    return urlsplit(url).netloc.lower() in ("vnit.ac.in", "www.vnit.ac.in")


def subsite_of(path, subsites):
    for s in sorted(subsites, key=len, reverse=True):
        if path.startswith(s):
            return s
    return "/"


# ------------------------------------------------------------ reading a page

def load(entry):
    return BeautifulSoup(gzip.decompress((CRAWL / "html" / entry["file"]).read_bytes()), "html.parser")


def page_title(soup):
    h1 = soup.select_one("h1.entry-title")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    og = soup.find("meta", property="og:title")
    raw = og["content"] if og and og.get("content") else (soup.title.get_text() if soup.title else "")
    title = SITE_SUFFIX.sub("", raw).strip(" |–—-")
    if title:
        return title
    h1 = soup.select_one("h1")
    return h1.get_text(" ", strip=True) if h1 else "VNIT Nagpur"


def page_date(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        return meta["content"][:10]
    t = soup.find("time", attrs={"datetime": True})
    return t["datetime"][:10] if t else ""


def page_kind(soup):
    classes = " ".join(soup.body.get("class", [])) if soup.body else ""
    return "post" if "single-post" in classes else "page"


def content_root(soup):
    """The element holding the page's own content, not the site's header and footer."""
    classes = " ".join(soup.body.get("class", [])) if soup.body else ""
    m = re.search(r"\b(?:page-id|postid)-(\d+)\b", classes)
    if m:
        el = soup.select_one(f'.elementor-{m.group(1)}[data-elementor-type]')
        if el:
            return el
    for sel in [".entry-content", "article", "main", "#content", ".site-main"]:
        el = soup.select_one(sel)
        if el:
            return el
    return soup.body


# ------------------------------------------------------------ menus

def menu_tree(ul, base):
    items = []
    for li in ul.find_all("li", recursive=False):
        a = li.find("a")
        if not a:
            continue
        label = a.get_text(" ", strip=True)
        href = (a.get("href") or "").strip()
        sub = li.find(["ul"], recursive=True)
        children = menu_tree(sub, base) if sub else []
        if not label:
            continue
        items.append({"label": label, "href": link_target(href, base), "children": children})
    return items


def find_menu(soup):
    for sel in ["#site-navigation-bottom-desktop", "nav.primary-menu", "header nav", ".hfe-nav-menu",
                ".ekit-menu-container", "#masthead nav", "nav"]:
        nav = soup.select_one(sel)
        if nav and nav.find("ul"):
            return nav.find("ul")
    return None


# ------------------------------------------------------------ cleaning content

def link_target(href, base, crawled=None):
    """Where a link should point on our site: vnit:/path/, an external URL, or '' (no link)."""
    if not href or href.startswith(("#", "javascript:")):
        return ""
    if href.startswith(("mailto:", "tel:")):
        return href.replace(" ", "")
    url = urljoin(base, href)
    if not url.startswith(("http://", "https://")):
        return ""
    if is_vnit(url):
        n = normalise(url)
        if crawled is None or n in crawled:
            return "vnit:" + urlsplit(n).path
    return url


def fix_widgets(root):
    for counter in root.select(".elementor-counter-number[data-to-value]"):
        counter.string = counter["data-to-value"]
    for title in root.select(".elementor-tab-mobile-title, .elementor-tab-title, .elementor-toggle-title"):
        title.name = "h3"
    for heading in root.select(".elementor-heading-title, .elementor-image-box-title, .elementor-icon-box-title"):
        if heading.name not in ("h1", "h2", "h3", "h4", "h5", "h6"):
            heading.name = "h3"


def strip_tree(root, base, crawled):
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for el in root.find_all(DROP):
        el.decompose()
    for el in root.find_all(class_=DROP_CLASSES):
        el.decompose()
    for el in root.find_all(True):
        if el.decomposed if hasattr(el, "decomposed") else False:
            continue
        name = el.name
        if name == "a":
            target = link_target(el.get("href", ""), base, crawled)
            if target:
                el.attrs = {"href": target}
            else:
                el.unwrap()
        elif name in ("td", "th"):
            el.attrs = {k: v for k, v in el.attrs.items() if k in ("colspan", "rowspan") and str(v).isdigit()}
        elif name in KEEP:
            el.attrs = {}
        elif name in BLOCKS:
            el.insert_before(" ")
            el.insert_after(" ")
            el.unwrap()
        else:
            el.unwrap()


def remove_empty(root):
    changed = True
    while changed:
        changed = False
        for el in root.find_all(True):
            if el.name in ("br", "hr", "td", "th"):
                continue
            if not el.get_text(strip=True):
                el.decompose()
                changed = True


def tidy_text(root):
    for s in root.find_all(string=True):
        if isinstance(s, NavigableString):
            new = re.sub(r"[ \t\r\n ]+", " ", str(s))
            if new != str(s):
                s.replace_with(new)


def heading_levels(root):
    """Page headings start at h2 (the page title is the only h1)."""
    for h in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(h.name[1])
        h.name = "h" + str(min(max(level, 2), 4))


def wrap_loose_text(root):
    """Bare text between blocks becomes a paragraph, so the page reads as paragraphs."""
    out, run = [], []
    block_tags = {"h2", "h3", "h4", "p", "ul", "ol", "table", "blockquote", "dl", "hr"}
    for node in list(root.contents):
        if getattr(node, "name", None) in block_tags:
            if run:
                out.append(run)
                run = []
            out.append(node)
        else:
            run.append(node)
    if run:
        out.append(run)
    root.clear()
    for item in out:
        if isinstance(item, list):
            text = "".join(str(n) for n in item).strip()
            if BeautifulSoup(text, "html.parser").get_text(strip=True):
                root.append(BeautifulSoup(f"<p>{text}</p>", "html.parser"))
        else:
            root.append(item)


def dedupe_blocks(root):
    """Drops a block that repeats the one just before it (Elementor often renders things twice)."""
    previous = None
    for el in root.find_all(["h2", "h3", "h4", "p", "ul", "ol", "table"], recursive=False):
        text = el.get_text(" ", strip=True)
        if text and text == previous:
            el.decompose()
        else:
            previous = text


def clean(root, base, crawled):
    fix_widgets(root)
    strip_tree(root, base, crawled)
    tidy_text(root)
    remove_empty(root)
    heading_levels(root)
    wrap_loose_text(root)
    dedupe_blocks(root)
    return str(root).strip()


def to_fragment(root, base, crawled):
    fragment = BeautifulSoup("<div></div>", "html.parser").div
    fragment.append(BeautifulSoup(str(root), "html.parser"))
    html = clean(fragment, base, crawled)
    return html[len("<div>"):-len("</div>")].strip() if html.startswith("<div>") else html


# ------------------------------------------------------------ whole run

def slug_for(path):
    return re.sub(r"[^a-zA-Z0-9]+", "_", path.strip("/")) or "home"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.setrecursionlimit(10000)
    manifest = json.loads((CRAWL / "manifest.json").read_text(encoding="utf-8"))
    saved = {url: e for url, e in manifest.items() if "file" in e and (CRAWL / "html" / e["file"]).exists()}
    crawled = set(saved)
    subsites = {"/" + s.strip("/") + "/" for s in __import__("crawl_site").SUBSITES + __import__("crawl_site").LINK_FOLLOW}
    PAGES.mkdir(parents=True, exist_ok=True)

    site, skipped, menus, finals, paths = [], [], {}, {}, {}
    for url, entry in sorted(saved.items()):
        final = entry.get("final_url", url)
        if final != url and final in saved:
            skipped.append({"url": url, "reason": f"redirects to {final}"})
            continue
        if final in finals:
            skipped.append({"url": url, "reason": f"same page as {finals[final]}"})
            continue
        finals[final] = url
        soup = load(entry)
        path = urlsplit(normalise(url)).path
        if path in paths:
            skipped.append({"url": url, "reason": f"same page as {paths[path]}"})
            continue
        paths[path] = url
        title = page_title(soup)
        if PRIVATE_TITLE.search(title):
            skipped.append({"url": url, "reason": "lists named individuals (privacy)", "title": title})
            continue
        sub = subsite_of(path, subsites)
        if path == sub or path == "/":
            ul = find_menu(soup)
            if ul is not None:
                menus[sub] = menu_tree(ul, url)
        root = content_root(soup)
        images = len(root.find_all("img"))
        body = to_fragment(root, url, crawled)
        slug = slug_for(path)
        (PAGES / f"{slug}.html").write_text(body, encoding="utf-8")
        site.append({"path": path, "slug": slug, "title": title, "kind": page_kind(soup),
                     "date": page_date(soup), "subsite": sub, "source_url": url,
                     "fetched": entry["fetched"], "images": images, "words": len(BeautifulSoup(body, "html.parser").get_text(" ").split())})

    (CONTENT / "site.json").write_text(json.dumps(site, indent=1, ensure_ascii=False), encoding="utf-8")
    (CONTENT / "menus.json").write_text(json.dumps(menus, indent=1, ensure_ascii=False), encoding="utf-8")
    (CONTENT / "skipped.json").write_text(json.dumps(skipped, indent=1, ensure_ascii=False), encoding="utf-8")
    posts = sum(1 for p in site if p["kind"] == "post")
    print(f"{len(site)} pages extracted ({posts} news posts), {len(skipped)} skipped, "
          f"{len(menus)} menus: {', '.join(sorted(menus))}")
    print(f"pages with no text left: {sum(1 for p in site if p['words'] == 0)}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
