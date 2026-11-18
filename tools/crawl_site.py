"""Fetches every page of vnit.ac.in, politely, so the demo site can show all of them.

The chatbot's crawl (vnit-chatbot/data/raw/) only kept the text of 81 pages.
This crawler finds every page the site lists in its WordPress sitemaps (the
main site plus each section and department sub-site), follows links inside the
sub-sites that have no sitemap, and saves each page's HTML (gzipped) to
crawl/html/, with crawl/manifest.json recording what was fetched and when.

Polite: obeys robots.txt, one request per second, the same user agent as the
chatbot's crawler. Resumable: pages already saved are skipped, so it can be
stopped and started again. It writes nothing outside vnit-website/crawl/.

    ~/anaconda3/python.exe tools/crawl_site.py            # discover and fetch everything
    ~/anaconda3/python.exe tools/crawl_site.py --limit 20 # a quick trial
"""
import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent.parent
CRAWL = HERE / "crawl"
HTML_DIR = CRAWL / "html"
MANIFEST = CRAWL / "manifest.json"

SITE = "https://vnit.ac.in"
USER_AGENT = "VNIT-Chatbot-Pilot/0.1 (student FYP project; contact via institute email)"
DELAY = 1.0
TIMEOUT = 30

# Sub-sites (separate WordPress installs) under vnit.ac.in, each with its own sitemap.
SUBSITES = [
    "section/academics", "section/hostel", "section/tnp", "section/rnc", "section/sports",
    "section/stores", "section/uba",
    "engineering/cse", "engineering/civil", "engineering/mech", "engineering/ece",
    "engineering/electrical", "engineering/chemical", "engineering/apm",
    "basic_science/chemistry", "basic_science/maths", "basic_science/hum",
]
# Parts of the site with no sitemap: followed by links from their front page.
LINK_FOLLOW = ["engineering/mining", "engineering/cvlsi", "arch", "basic_science/phy", "engineering/meta"]

SKIP = re.compile(
    r"/wp-admin|/wp-login|/wp-json|/feed/?$|/xmlrpc|/register/?$|/my-bookings|/my-account|/login|"
    r"/events/(locations|tags|categories)|/cart|/checkout|/author/|/tag/|/page/\d+|"
    r"\.(pdf|jpe?g|png|gif|webp|svg|zip|rar|docx?|xlsx?|pptx?|mp4|mp3)$|/wp-content/",
    re.I)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def normalise(url):
    """https, no query or fragment, trailing slash: one spelling per page."""
    parts = urlsplit(url)
    path = re.sub(r"/+", "/", parts.path or "/")
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return urlunsplit(("https", "vnit.ac.in", path, "", ""))


def on_site(url):
    host = urlsplit(url).netloc.lower()
    return host in ("vnit.ac.in", "www.vnit.ac.in") and not SKIP.search(urlsplit(url).path)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.geturl(), resp.headers.get("Content-Type", ""), resp.read()


class Crawler:
    def __init__(self):
        self.robots = urllib.robotparser.RobotFileParser(SITE + "/robots.txt")
        self.robots.read()
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
        self.last = 0.0

    def polite_get(self, url):
        wait = DELAY - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        return get(url)

    def sitemap_urls(self, base):
        """Every page and post URL listed in a WordPress sitemap index."""
        urls = []
        try:
            _, _, _, body = self.polite_get(f"{SITE}/{base}wp-sitemap.xml".replace("//wp", "/wp"))
        except (urllib.error.URLError, OSError):
            return urls
        for sub in re.findall(r"<loc>([^<]+)</loc>", body.decode("utf-8", "replace")):
            if re.search(r"users|taxonomies", sub):
                continue
            try:
                _, _, _, xml = self.polite_get(sub)
            except (urllib.error.URLError, OSError):
                continue
            urls += re.findall(r"<loc>([^<]+)</loc>", xml.decode("utf-8", "replace"))
        return urls

    def discover(self):
        found = self.sitemap_urls("")
        for base in SUBSITES:
            found += self.sitemap_urls(base + "/")
            found.append(f"{SITE}/{base}/")
        found.append(SITE + "/")
        return [normalise(u) for u in found if on_site(u)]

    def save(self, url, html, final_url, status):
        name = re.sub(r"[^a-zA-Z0-9]+", "_", urlsplit(url).path.strip("/")) or "home"
        name = name[:120]
        (HTML_DIR / f"{name}.html.gz").write_bytes(gzip.compress(html))
        self.manifest[url] = {"file": f"{name}.html.gz", "final_url": final_url, "status": status,
                              "fetched": date.today().isoformat()}

    def fetch(self, url):
        """Fetches one page; returns its HTML bytes, or None."""
        if not self.robots.can_fetch(USER_AGENT, url):
            self.manifest[url] = {"status": "robots"}
            return None
        try:
            status, final_url, ctype, body = self.polite_get(url)
        except urllib.error.HTTPError as e:
            self.manifest[url] = {"status": e.code}
            return None
        except (urllib.error.URLError, OSError) as e:
            self.manifest[url] = {"status": f"error: {type(e).__name__}"}
            return None
        if "html" not in ctype:
            self.manifest[url] = {"status": f"not html: {ctype}"}
            return None
        self.save(url, body, normalise(final_url), status)
        return body

    def write_manifest(self):
        MANIFEST.write_text(json.dumps(self.manifest, indent=1, sort_keys=True), encoding="utf-8")

    def run(self, limit=None):
        HTML_DIR.mkdir(parents=True, exist_ok=True)
        queue = list(dict.fromkeys(self.discover()))
        follow = [normalise(f"{SITE}/{b}/") for b in LINK_FOLLOW]
        queue += [u for u in follow if u not in queue]
        print(f"{len(queue)} pages from sitemaps and sub-site front pages", flush=True)
        seen, done = set(queue), 0
        while queue and (limit is None or done < limit):
            url = queue.pop(0)
            entry = self.manifest.get(url)
            if entry and "file" in entry and (HTML_DIR / entry["file"]).exists():
                body = gzip.decompress((HTML_DIR / entry["file"]).read_bytes())
            else:
                body = self.fetch(url)
                done += 1
                if done % 25 == 0:
                    self.write_manifest()
                    print(f"  {done} fetched, {len(queue)} queued", flush=True)
            if body is None:
                continue
            for prefix in follow:
                if url.startswith(prefix):
                    for link in self.links_under(body, url, prefix):
                        if link not in seen:
                            seen.add(link)
                            queue.append(link)
        self.write_manifest()
        saved = sum(1 for e in self.manifest.values() if "file" in e)
        print(f"done: {saved} pages saved, {len(self.manifest) - saved} skipped or failed", flush=True)

    def links_under(self, body, url, prefix):
        parser = LinkParser()
        parser.feed(body.decode("utf-8", "replace"))
        links = (normalise(urljoin(url, h)) for h in parser.links)
        return [l for l in links if l.startswith(prefix) and on_site(l)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="stop after fetching this many pages")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    Crawler().run(args.limit)


if __name__ == "__main__":
    main()
