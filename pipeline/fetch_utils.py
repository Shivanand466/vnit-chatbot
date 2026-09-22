"""
Real HTTP fetching for crawl.py and recrawl.py.

Needs actual internet access to vnit.ac.in, which Claude's own tooling
(cloud sandbox + device-bridge shell) cannot reach -- confirmed repeatedly,
see README.md. This module is meant to be imported and run by Claude Code
(or any normal process) on a machine with real internet, per
RUNBOOK-FOR-CLAUDE-CODE.md. It has no Claude-specific dependency; it's
plain requests + BeautifulSoup.
"""
import time
import re
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "VNIT-Chatbot-Pilot/0.1 (student FYP project; contact via institute email)"
REQUEST_DELAY_SECONDS = 1.0  # be polite -- one request per second, not a hammer
TIMEOUT = 20

_robots_cache = {}


def _get_robots_parser(base_url: str):
    origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    if origin not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(urljoin(origin, "/robots.txt"))
        try:
            rp.read()
        except Exception:
            rp = None  # if robots.txt itself can't be fetched, caller should be conservative
        _robots_cache[origin] = rp
    return _robots_cache[origin]


def is_allowed(url: str) -> bool:
    rp = _get_robots_parser(url)
    if rp is None:
        return True  # no robots.txt reachable -- don't block on that alone
    return rp.can_fetch(USER_AGENT, url)


def fetch_page(url: str):
    """Fetch one URL, return (title, clean_text, content_type, raw_html) or
    raise. Strips nav/header/footer/script/style before extracting text --
    same "real content only" goal as the WebFetch prompts used during the
    original pilot crawl, just done with a real HTTP client + BeautifulSoup
    instead of Claude's tool. raw_html is returned too (even though this
    function already parsed it) so callers like crawl.py can pull links out
    of the same response without a second request."""
    if not is_allowed(url):
        raise PermissionError(f"robots.txt disallows fetching {url}")

    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")

    if "text/html" not in content_type:
        return None, None, content_type, None  # caller decides what to do with non-HTML (e.g. PDFs)

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["nav", "header", "footer", "script", "style", "noscript", "form"]):
        tag.decompose()

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excess blank lines

    return title, text, content_type, resp.text


def extract_internal_links(url: str, html: str, allowed_netloc: str):
    """All same-site links found on a page, absolute-ized, query/fragment
    stripped, restricted to allowed_netloc. Used by crawl.py's BFS."""
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        absolute = urljoin(url, a["href"].split("#")[0])
        parsed = urlparse(absolute)
        if parsed.netloc != allowed_netloc:
            continue
        if parsed.scheme not in ("http", "https"):
            continue
        # skip obvious non-page files this pilot isn't set up to parse yet.
        # NOTE (2026-09-21, see REPORT2.md): .pdf added to this list -- it was
        # missing before, so crawl.py was downloading every linked PDF in
        # full (fetch_page reads content_type and returns None for non-HTML)
        # only to discard it, wasting bandwidth and politeness-delay time on
        # files this pilot doesn't ingest yet. PDF ingestion is still on the
        # "not built" list in README.md; this just stops fetching them
        # pointlessly until that's built.
        if re.search(r"\.(jpg|jpeg|png|gif|svg|zip|docx?|xlsx?|pptx?|pdf)$", parsed.path, re.IGNORECASE):
            continue
        clean = parsed._replace(query="", fragment="").geturl()
        links.add(clean)
    return links
