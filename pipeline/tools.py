"""
The agent's tools: what the planner (planner.py) may do besides answering.

    search_vnit       search all of VNIT's pages and documents with new words
    find_documents    find pages/documents by what their title says
    read_document     search inside one page or document only
    calculate         exact arithmetic (fee totals, differences, counts)

Why these four. Each one answers a failure measured in EXPERIMENTS-LOG.md:
- one search with the student's own words sometimes misses, and a second
  search with other words (a synonym, the document's own vocabulary) is the
  most ordinary thing a person does next;
- the 2025-26 placement figures sit in one paragraph of the T&P page, which
  ranks 293rd corpus-wide behind hundreds of company-list passages (§16).
  Finding the page by its title first and then searching only inside it is the
  "page-level retrieval stage" §16 called for, and the agent can decide when
  that is needed instead of it being forced on every question;
- arithmetic done "in the head" by a language model is a classic source of
  wrong figures; a calculator makes it exact, and the verifier (verifier.py)
  can then trust the result.

Every passage the agent sees is registered in an `Evidence` log and labelled
[P1], [P2], ... so the answer can cite it, the chat page can link it, and the
verifier can check each figure against exactly what the model was shown.
"""
import ast
import operator
import os
import re
import sqlite3
from pathlib import Path

import generate
import query
import slots
from programme_terms import contradicts, years

# How much a tool returns. Each tool round adds to a prompt that Groq's free
# tier caps at 8,000 tokens a minute, so a tool returns 3 passages, not the
# first search's 7+. Passages are cut at the same length as the first search's
# (generate.MAX_CHUNK_CHARS): at 700 the T&P paragraph lost its second half,
# "170 organisations", the very figure read_document was opened to find.
TOOL_PASSAGE_CHARS = generate.MAX_CHUNK_CHARS
TOOL_PASSAGES = 3
MAX_DOCUMENTS_LISTED = 6


# ---------------------------------------------------------------------------
# Evidence: every passage shown to the model, numbered.
# ---------------------------------------------------------------------------

class Evidence:
    """The passages the agent has been shown, in order, each with a label."""

    def __init__(self):
        import threading

        self.passages = []   # dicts: pid, result, text (as shown to the model)
        self._by_key = {}
        # Agent v2 runs up to three tools at once (agent_loop.py); two of them
        # registering a passage at the same moment must not get the same label.
        self._lock = threading.Lock()

    @staticmethod
    def _key(r):
        # The whole text, not its start: table rows from one document share a
        # long lead-in, and keyed on the first 80 characters every row of a fee
        # sheet would have been taken for the first one.
        return (r["source_url"], r["text"])

    def add(self, r: dict, text: str, origin: str = "tool"):
        """Register a passage; returns (pid, is_new). `origin` is "first" for the first search."""
        key = self._key(r)
        with self._lock:
            if key in self._by_key:
                return self._by_key[key], False
            pid = f"P{len(self.passages) + 1}"
            self.passages.append({"pid": pid, "result": r, "text": text, "origin": origin})
            self._by_key[key] = pid
            return pid, True

    def get(self, pid: str):
        for p in self.passages:
            if p["pid"] == pid:
                return p
        return None

    def texts(self) -> list:
        return [p["text"] for p in self.passages]

    def render(self, results, max_chars=None) -> str:
        """Register `results` and format them for a prompt.

        A passage already shown is referred to by its label only, so a repeat
        search costs a few tokens instead of the whole passage again.
        """
        blocks = []
        for r in results:
            text = r["text"]
            if max_chars and len(text) > max_chars:
                text = text[:max_chars].rsplit(" ", 1)[0] + "..."
            pid, new = self.add(r, text)
            if new:
                blocks.append(f"[{pid} · doc {doc_id(r['source_url'])}] "
                              f"{generate.passage_header(r)[1:-1]}\n{text}")
            else:
                blocks.append(f"[{pid}] (already shown above)")
        return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Document catalogue: short, stable ids the model can quote back.
# ---------------------------------------------------------------------------

def _catalogue():
    return query.list_sources()


def doc_id(url: str) -> str:
    """A short id for a page or document ("S57"), stable while the index is unchanged."""
    for i, s in enumerate(_catalogue()):
        if s["url"] == url:
            return f"S{i}"
    return "?"


def _resolve_document(ref: str):
    """Find a catalogue entry from what the model wrote: an id, a URL or a title."""
    ref = (ref or "").strip().strip("[]")
    sources = _catalogue()
    m = re.fullmatch(r"(?:doc\s*)?S(\d+)", ref, re.I)
    if m and int(m.group(1)) < len(sources):
        return sources[int(m.group(1))]
    for s in sources:
        if ref and ref == s["url"]:
            return s
    low = ref.lower()
    if len(low) >= 4:
        exact = [s for s in sources if s["title"].lower() == low]
        if exact:
            return exact[0]
        partial = [s for s in sources if low in s["title"].lower()]
        if partial:
            return partial[0]
    return None


_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "of", "and", "for", "in", "on", "a", "an", "to", "at", "vnit", "nagpur",
         "document", "documents", "page", "pdf", "notice", "with", "by", "is", "about",
         "how", "many", "much", "what", "when", "who", "which", "where", "does", "did", "do",
         "are", "was", "were", "came", "come", "get", "got", "give", "tell", "me", "there"}


def _words(text: str) -> set:
    """Content-word stems, without numbers.

    Stems are the first five letters, so "placed" meets "Placement" and
    "companies" meets "Company". Numbers are left out: years are compared
    separately, as academic years, or every 2025-26 notice would match any
    question naming 2025-26.
    """
    return {w[:5] for w in _WORD.findall(text.lower())
            if w not in _STOP and len(w) > 1 and not w.isdigit()}


_title_idf = {"mtime": None, "idf": None, "words": None}


def _title_words():
    """Each title's stems, and how rare each stem is across all titles (IDF)."""
    import math

    if _title_idf["mtime"] != query._index_cache["mtime"]:
        sources = _catalogue()
        words = [_words(f"{s['title']} {s['url'].rsplit('/', 2)[-2] if '/' in s['url'] else ''}")
                 for s in sources]
        df = {}
        for ws in words:
            for w in ws:
                df[w] = df.get(w, 0) + 1
        _title_idf["idf"] = {w: math.log(len(sources) / n) for w, n in df.items()}
        _title_idf["words"] = words
        _title_idf["mtime"] = query._index_cache["mtime"]
    return _title_idf["words"], _title_idf["idf"]


def _title_scores(keywords: str):
    """Score every catalogue entry's title against `keywords`.

    Word overlap does most of the work (titles are short and literal: "Placement
    and Internship Report 2025-2026"), weighted by rarity so that "placement"
    counts for far more than "students", which a hundred titles contain. An
    academic year named in the keywords must match the title's when the title
    has one, and title embeddings break ties and catch synonyms.
    """
    sources = _catalogue()
    title_words, idf = _title_words()
    want = _words(keywords)
    total = sum(idf.get(w, 0.0) for w in want) or 1.0
    want_years = years(keywords)
    sims = _title_similarities(keywords)
    scored = []
    for i, s in enumerate(sources):
        overlap = sum(idf.get(w, 0.0) for w in want & title_words[i]) / total
        title_years = years(s["title"])
        if want_years and title_years and title_years.isdisjoint(want_years):
            overlap *= 0.3  # names a different academic year
        elif want_years and title_years & want_years:
            # Same year: a boost in proportion, so a title that shares only the
            # year and the word "students" stays below one about the subject.
            overlap *= 1.3
        score = overlap + 0.5 * sims[i]
        # The same programme/year/gender filter the passage search uses
        # (programme_terms.py): an M.Tech fee sheet is the wrong document for a
        # B.Tech question however similar its title.
        if contradicts(keywords, s["title"]):
            score *= 0.3
        scored.append((score, i))
    scored.sort(reverse=True)
    return scored


_title_vectors = {"mtime": None, "matrix": None}


def _title_similarities(keywords: str):
    """Embedding similarity of `keywords` to every title (zeros if no embedding model)."""
    import numpy as np

    sources = _catalogue()
    data = query.load_index()
    if data.get("type") != "embeddings":
        return np.zeros(len(sources))
    model = query._get_embedding_model(data["model_name"])
    if _title_vectors["mtime"] != query._index_cache["mtime"]:
        _title_vectors["matrix"] = model.encode([s["title"] for s in sources],
                                                normalize_embeddings=True)
        _title_vectors["mtime"] = query._index_cache["mtime"]
    q = model.encode([keywords], normalize_embeddings=True)[0]
    return _title_vectors["matrix"] @ q


# ---------------------------------------------------------------------------
# Calculator: arithmetic only, never eval().
# ---------------------------------------------------------------------------

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def safe_calculate(expression: str) -> float:
    """Evaluate +, -, *, /, %, ** and brackets over numbers. Anything else is refused.

    Indian digit grouping ("1,25,000") and "x"/"×" for multiplication are
    accepted, because that is how the fee sheets and the model write them.
    """
    expr = (expression or "").replace("×", "*").replace("÷", "/").replace("₹", "")
    expr = re.sub(r"(?<=\d),(?=\d)", "", expr)
    expr = re.sub(r"(?<=[\d)\s])x(?=[\s\d(])", "*", expr, flags=re.I)
    if len(expr) > 200:
        raise ValueError("expression too long")
    tree = ast.parse(expr.strip(), mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("only numbers and + - * / % ( ) are allowed")

    value = ev(tree)
    return int(value) if float(value).is_integer() else round(value, 4)


# ---------------------------------------------------------------------------
# The tools as the model sees them (OpenAI-compatible function schemas).
# ---------------------------------------------------------------------------

SCHEMAS = [
    {"type": "function", "function": {
        "name": "search_vnit",
        "description": "Search all of VNIT Nagpur's web pages and documents for passages "
                       "matching a query. Use it when the passages you have do not answer "
                       "the question: rephrase with other words, the words a notice or fee "
                       "sheet would use, or one part of a multi-part question.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to search for, as a short question or phrase."}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "find_documents",
        "description": "Find VNIT pages and documents by their title, e.g. 'placement report "
                       "2025-26', 'academic calendar winter 2026', 'hostel fees first year girls'. "
                       "Returns titles, dates and document ids (like S57) to use with read_document.",
        "parameters": {"type": "object", "properties": {
            "keywords": {"type": "string", "description": "Words the title is likely to contain."}},
            "required": ["keywords"]}}},
    {"type": "function", "function": {
        "name": "read_document",
        "description": "Search inside ONE page or document only, by its id (e.g. S57, from "
                       "find_documents or from a passage label). Use it when you know which "
                       "document should hold the answer but the passage you need was not shown.",
        "parameters": {"type": "object", "properties": {
            "document_id": {"type": "string", "description": "The document id, e.g. S57."},
            "query": {"type": "string", "description": "What to look for inside that document."}},
            "required": ["document_id", "query"]}}},
    {"type": "function", "function": {
        "name": "lookup_table",
        "description": "Look up rows of the tables in VNIT's documents (fee sheets, hostel fee "
                       "sheets, exam timetables, academic calendars). Use it for fee amounts and "
                       "dated table entries, e.g. keywords 'tuition fee' with programme 'msc', or "
                       "'mid sem slot A'. The filters are optional; rows that do not state a "
                       "filtered detail are still returned, after the ones that match it.",
        "parameters": {"type": "object", "properties": {
            "keywords": {"type": "string", "description": "Words in the row, its column or the document title."},
            "programme": {"type": "string", "enum": list(slots.LABELS["programme"])},
            "gender": {"type": "string", "enum": list(slots.LABELS["gender"])},
            "category": {"type": "string", "enum": list(slots.LABELS["category"])},
            "study_year": {"type": "string", "enum": list(slots.LABELS["study_year"])},
            "academic_year": {"type": "string", "description": "Like 2026-27."}},
            "required": ["keywords"]}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "Exact arithmetic, e.g. '125000 * 4' or '32650 - 32150'. Use it for any "
                       "total, difference or multiplication in your answer.",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "An arithmetic expression."}},
            "required": ["expression"]}}},
]

TOOL_NAMES = [s["function"]["name"] for s in SCHEMAS]


def active_schemas(v2: bool = False) -> list:
    """The tools offered to the model: lookup_table only when its database exists and
    LOOKUP_TABLE is not "off" (for the ablations of EXPERIMENTS-LOG). `v2` adds
    agent v2's tools (V2_SCHEMAS); v1's planner never asks for them."""
    off = os.environ.get("LOOKUP_TABLE", "on").strip().lower() in ("off", "0", "false", "no")
    schemas = SCHEMAS + (v2_schemas() if v2 else [])
    if off or not FACTS_PATH.exists():
        return [s for s in schemas if s["function"]["name"] != "lookup_table"]
    return schemas


def v2_schemas() -> list:
    """Agent v2's extra tools; fetch_vnit_page only while LIVE_PAGES is not "off"."""
    live = os.environ.get("LIVE_PAGES", "on").strip().lower() not in ("off", "0", "false", "no")
    return [s for s in V2_SCHEMAS if live or s["function"]["name"] != "fetch_vnit_page"]


# Descriptions are kept under 25 words: every one is sent with every round.
V2_SCHEMAS = [
    {"type": "function", "function": {
        "name": "latest_notices",
        "description": "The newest VNIT notices and documents, newest first, optionally of one "
                       "category. For 'any new notice about fees?' or 'what's the latest on scholarships?'.",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "enum": ["fees", "academics", "hostel", "scholarship",
                                                    "placement", "admission", "recruitment"]},
            "n": {"type": "integer", "description": "How many, 1 to 8 (default 5)."}}}}},
    {"type": "function", "function": {
        "name": "fetch_vnit_page",
        "description": "Open a live page on vnit.ac.in and read its current text. For checking "
                       "what the website says now, or a page the search lacks.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "A https://vnit.ac.in/... address."}},
            "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "today",
        "description": "Today's date in India (IST). For 'is the deadline over?' or 'when is the next holiday?'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "contact_office",
        "description": "The VNIT office to contact about a topic (hostel, fees, exams, ...), with "
                       "its email and phone.",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string", "description": "What the student needs help with, e.g. 'hostel refund'."}},
            "required": ["topic"]}}},
]


# ---------------------------------------------------------------------------
# latest_notices: the newest converted documents, from the document inventory
# ---------------------------------------------------------------------------

DOCUMENTS = Path(__file__).parent.parent / "data" / "documents"
RAW = Path(__file__).parent.parent / "data" / "raw"
NOTICE_CATEGORIES = {
    "fees": r"fees?|payment|remission|refund|tuition|challan",
    "academics": r"calendar|exam\w*|time\s*-?table|semester|course|registration|academic|result|"
                 r"syllabus|curriculum|convocation|holiday",
    "hostel": r"hostels?|mess|warden",
    "scholarship": r"scholarships?|fellowships?|stipend",
    "placement": r"placements?|internships?|training\s*&\s*placement|t\s*&\s*p",
    "admission": r"admissions?|brochure|counsell?ing|josaa|csab|dasa|reporting|seat\s+matrix",
    "recruitment": r"recruitment|vacanc\w*|advertisement|walk-?in|interview|post\s+of|faculty\s+position",
}
MAX_NOTICES = 8


def latest_notices(category: str = "", n: int = 5) -> list:
    """The newest documents that were converted and kept (status "ok", text in data/raw),
    newest first, as result dicts: title, date, link and the page that lists it."""
    import json

    inventory = json.loads((DOCUMENTS / "inventory.json").read_text(encoding="utf-8"))
    status = json.loads((DOCUMENTS / "status.json").read_text(encoding="utf-8"))
    pattern = re.compile(rf"\b(?:{NOTICE_CATEGORIES[category]})\b", re.I) if category in NOTICE_CATEGORIES else None
    found = []
    for key, st in status.items():
        entry = inventory.get(key)
        if not entry or not isinstance(st, dict) or st.get("result") != "ok":
            continue
        if not st.get("file") or not (RAW / st["file"]).exists():
            continue  # excluded, held aside or never converted
        title = (st.get("title") or entry.get("link_text") or entry.get("name") or "").strip()
        if pattern and not pattern.search(f"{title} {entry.get('name', '')}"):
            continue
        day = (entry.get("modifiedTime") or "")[:10]
        found.append({"text": f"{title} — dated {day or 'undated'} — listed on {entry.get('found_on', 'vnit.ac.in')}",
                      "title": title, "source_url": entry["url"], "fetched": day,
                      "score": 0.0, "rerank": None})
    found.sort(key=lambda r: r["fetched"], reverse=True)
    return found[:max(1, min(MAX_NOTICES, int(n or 5)))]


# ---------------------------------------------------------------------------
# fetch_vnit_page: a live page, only on vnit.ac.in, cached for a day
# ---------------------------------------------------------------------------

PAGE_CACHE = Path(__file__).parent.parent / "data" / "cache" / "pages"
PAGE_CHARS = 2500
PAGE_TIMEOUT = 10
PAGE_CACHE_SECONDS = 24 * 3600
_last_fetch = [0.0]


def vnit_url(url: str):
    """The URL if it is an http(s) address on vnit.ac.in or one of its sub-sites, else None.

    The host is compared as a whole, so "vnit.ac.in.evil.com" and
    "evilvnit.ac.in" are refused.
    """
    from urllib.parse import urlparse

    try:
        parts = urlparse((url or "").strip())
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not (host == "vnit.ac.in" or host.endswith(".vnit.ac.in")):
        return None
    return parts.geturl()


def page_text(html: str) -> tuple:
    """(title, readable text) of a page's HTML, read exactly as the crawler reads pages."""
    import fetch_utils

    title, text = fetch_utils.html_to_text(html)
    return title, re.sub(r"\s+", " ", text or "").strip()


def _cached(url: str):
    import hashlib
    import json
    import time

    path = PAGE_CACHE / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("at", 0) < PAGE_CACHE_SECONDS:
            return path, data
    return path, None


def _crawled_copy(url: str):
    """The page's text as crawled (from the index), for when the live site can't be reached."""
    want = url.rstrip("/")
    for s in _catalogue():
        if s["url"].rstrip("/") == want:
            chunks = query.load_index()["chunks"]
            return s["title"], " ".join(chunks[i]["text"] for i in s["chunk_ids"])
    return None


def fetch_vnit_page(url: str, fetch=None) -> dict:
    """{"title", "text", "url", "from"} for a vnit.ac.in page; "from" is live, cache or crawl.

    One request a second at most, robots.txt respected, the crawler's user
    agent, a 10 s timeout, and a day's cache in data/cache/pages/. `fetch`
    (url -> html) replaces the network in tests.
    """
    import json
    import time

    import fetch_utils
    import requests

    safe = vnit_url(url)
    if not safe:
        raise ValueError("only pages on vnit.ac.in can be opened")
    path, cached = _cached(safe)
    if cached:
        return dict(cached, **{"from": "cache"})
    try:
        if fetch is None:
            if not fetch_utils.is_allowed(safe):
                raise PermissionError("robots.txt does not allow it")
            wait = fetch_utils.REQUEST_DELAY_SECONDS - (time.time() - _last_fetch[0])
            if wait > 0:
                time.sleep(wait)
            _last_fetch[0] = time.time()
            resp = requests.get(safe, headers={"User-Agent": fetch_utils.USER_AGENT}, timeout=PAGE_TIMEOUT)
            resp.raise_for_status()
            html = resp.text
        else:
            html = fetch(safe)
        title, text = page_text(html)
    except Exception:
        copy = _crawled_copy(safe)
        if copy is None:
            raise
        title, text = copy
        return {"title": title, "text": text[:PAGE_CHARS], "url": safe, "from": "crawl"}
    page = {"title": title or safe, "text": text[:PAGE_CHARS], "url": safe, "at": time.time()}
    PAGE_CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    return dict(page, **{"from": "live"})


# ---------------------------------------------------------------------------
# today and contact_office
# ---------------------------------------------------------------------------

def today_ist():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


CONTACTS = Path(__file__).parent.parent / "data" / "contacts.json"


def contact_for(topic: str):
    """The office for a topic, from data/contacts.json (copied by hand from VNIT's pages)."""
    import json
    import router

    contacts = {k: v for k, v in json.loads(CONTACTS.read_text(encoding="utf-8")).items()
                if not k.startswith("_")}
    return contacts.get(router.intent(topic or "")) or contacts.get("other")


def run_v2_tool(name: str, args: dict, evidence: Evidence):
    """Agent v2's tools, or None for any other name (run_tool handles those)."""
    if name == "latest_notices":
        category = str(args.get("category") or "").strip().lower()
        rows = latest_notices(category, args.get("n") or 5)
        if not rows:
            return {"observation": "No notices found in that category.",
                    "summary": f"Looked for the latest {category or ''} notices: none found"}
        return {"observation": "Newest first:\n\n" + evidence.render(rows),
                "summary": f"Listed the {len(rows)} newest {category + ' ' if category else ''}notices: "
                           + _titles(rows, 2)}
    if name == "fetch_vnit_page":
        url = str(args.get("url") or "")
        if not vnit_url(url):
            return {"observation": "Refused: only pages on vnit.ac.in can be opened.",
                    "summary": f"Refused to open a page outside vnit.ac.in ({url[:60]})"}
        page = fetch_vnit_page(url)
        result = {"text": page["text"], "title": page["title"], "source_url": page["url"],
                  "fetched": "", "score": 0.0, "rerank": None}
        where = {"live": "Opened the live page", "cache": "Opened the page (saved copy from today)",
                 "crawl": "The live site could not be reached, so read the crawled copy of"}[page["from"]]
        return {"observation": evidence.render([result]),
                "summary": f"{where} “{page['title']}”"}
    if name == "today":
        day = today_ist()
        result = {"text": f"Today's date (from the server clock, India time) is {day:%d %B %Y} "
                          f"({day:%d/%m/%Y}, a {day:%A}).",
                  "title": "Today's date", "source_url": "about:today", "fetched": "",
                  "score": 0.0, "rerank": None}
        return {"observation": evidence.render([result]), "summary": f"Checked today's date: {day:%d %B %Y}"}
    if name == "contact_office":
        office = contact_for(str(args.get("topic") or ""))
        result = {"text": f"{office['office']} — email {office['email']}, phone {office['phone']}.",
                  "title": office["office"], "source_url": office["source_url"], "fetched": "",
                  "score": 0.0, "rerank": None}
        return {"observation": evidence.render([result]),
                "summary": f"Looked up whom to contact: {office['office']}"}
    return None


def run_tool(name: str, args: dict, evidence: Evidence) -> dict:
    """Run one tool call. Returns {"observation": text for the model, "summary": for the trace,
    and "value" for calculate}. Never raises: a bad call becomes an observation the
    model can correct, which is how a person would handle a typo too."""
    try:
        if name == "search_vnit":
            q = str(args.get("query", "")).strip()
            if not q:
                return {"observation": "Error: query is empty.", "summary": "empty search"}
            results = query.retrieve(q, k=TOOL_PASSAGES)
            obs = evidence.render(results, TOOL_PASSAGE_CHARS) or "No passages found."
            obs += "\n\n" + matching_titles(q, exclude=[r["source_url"] for r in results])
            return {"observation": obs,
                    "summary": f"Searched for “{q}”: {_titles(results)}"}

        if name == "find_documents":
            kw = str(args.get("keywords", "")).strip()
            if not kw:
                return {"observation": "Error: keywords are empty.", "summary": "empty document search"}
            sources = _catalogue()
            top = [sources[i] for _, i in _title_scores(kw)[:MAX_DOCUMENTS_LISTED]]
            lines = [f"S{sources.index(s)}: {s['title']}"
                     + (f" (dated {s['date']})" if s["date"] and generate._is_document(s["url"]) else "")
                     + f" — {len(s['chunk_ids'])} passages" for s in top]
            return {"observation": "Matching pages and documents:\n" + "\n".join(lines),
                    "summary": f"Looked up documents titled like “{kw}”: "
                               + "; ".join(s["title"] for s in top[:3])}

        if name == "read_document":
            ref = str(args.get("document_id", ""))
            q = str(args.get("query", "")).strip()
            src = _resolve_document(ref)
            if src is None:
                return {"observation": f"Error: no document with id {ref!r}. Use find_documents "
                                       f"to get a valid id like S57.",
                        "summary": f"Tried to open an unknown document ({ref})"}
            results = query.retrieve_within(q or src["title"], [src["url"]], k=TOOL_PASSAGES)
            obs = evidence.render(results, TOOL_PASSAGE_CHARS) or "That document has no matching passages."
            return {"observation": obs,
                    "summary": f"Looked inside “{src['title']}” for “{q}”"}

        if name == "lookup_table":
            kw = str(args.get("keywords", "")).strip()
            tags = {k: str(args[k]) for k in TABLE_TAGS if args.get(k)}
            rows = lookup_table(kw, **tags)
            if not rows:
                return {"observation": "No table rows match. Try other keywords or fewer filters.",
                        "summary": f"Looked up table rows for “{kw}”: none found"}
            return {"observation": evidence.render(rows, TOOL_PASSAGE_CHARS),
                    "summary": f"Looked up table rows for “{kw}”"
                               + (f" ({', '.join(tags.values())})" if tags else "")
                               + f": {len(rows)} rows from {_titles(rows)}"}

        if name == "calculate":
            expr = str(args.get("expression", ""))
            value = safe_calculate(expr)
            return {"observation": f"{expr} = {value}", "summary": f"Calculated {expr} = {value}",
                    "value": value}

        v2 = run_v2_tool(name, args, evidence)
        if v2 is not None:
            return v2
        return {"observation": f"Error: unknown tool {name!r}. Available: {', '.join(TOOL_NAMES)}.",
                "summary": f"Asked for an unknown tool ({name})"}
    except Exception as e:  # a tool must never take the whole answer down
        return {"observation": f"Error running {name}: {type(e).__name__}: {e}",
                "summary": f"{name} failed ({type(e).__name__})"}


# ---------------------------------------------------------------------------
# Table lookup: rows of the documents' tables, from data/processed/facts.db.
# ---------------------------------------------------------------------------

FACTS_PATH = Path(__file__).parent.parent / "data" / "processed" / "facts.db"
TABLE_TAGS = ("programme", "gender", "category", "study_year", "academic_year")
TABLE_ROWS = 8
_LEAD_IN_CHARS = 140


def lookup_table(keywords: str, limit: int = TABLE_ROWS, **tags) -> list:
    """Table rows matching `keywords`, filtered by the tags given, as result dicts.

    The query is always parameterised and built here: the model chooses
    keywords and tag values, never SQL. The database holds one record per
    cell; a result is one whole table row (its cells joined), because a lone
    cell -- "2026-27 1st YR: 64200" -- means nothing without the row's label
    and its "Total" cell. Keywords are word stems (as in find_documents),
    matched in the row's cells, label, lead-in and document title; a row must
    match at least half of them.

    A tag filter keeps rows that state that value *or state none*, as
    programme_terms.py does for passages: most fee-sheet rows name their group
    only in the title, if at all. Rows that do state it come first, then rows
    matching more keywords, then rows holding figures, then newer documents.
    """
    words = sorted(_words(keywords))
    if not words or not FACTS_PATH.exists():
        return []
    valid = {k: v for k, v in tags.items()
             if (k == "academic_year" and re.fullmatch(r"20\d{2}-\d{2}", v))
             or (k in slots.LABELS and v in slots.LABELS[k])}
    row_text = ("(lead_in || ' ' || row_label || ' ' || title || ' ' "
                "|| group_concat(column || ' ' || value, ' '))")
    hits = " + ".join([f"({row_text} LIKE ?)"] * len(words))
    exact = " + ".join([f"({k} IS ?)" for k in valid]) or "0"  # IS: 0 or 1, never NULL
    where = " AND ".join([f"({k} = ? OR {k} IS NULL)" for k in valid]) or "1"
    sql = (f"SELECT doc_url, title, date, lead_in, row_label, "
           f"group_concat(column || ': ' || value, '; '), {hits} AS hits, {exact} AS exact, "
           f"MAX(number IS NOT NULL) AS figures FROM facts WHERE {where} "
           f"GROUP BY doc_url, lead_in, row_label HAVING hits >= ? "
           f"ORDER BY exact DESC, hits DESC, figures DESC, date DESC LIMIT ?")
    likes = [f"%{w}%" for w in words]
    params = (likes + list(valid.values()) + list(valid.values())
              + [(len(words) + 1) // 2, limit])
    with sqlite3.connect(f"file:{FACTS_PATH}?mode=ro", uri=True) as db:
        rows = db.execute(sql, params).fetchall()
    results = []
    for url, title, date, lead_in, row_label, cells, _hits, _exact, _figures in rows:
        lead = lead_in if len(lead_in) <= _LEAD_IN_CHARS else lead_in[:_LEAD_IN_CHARS] + "..."
        results.append({"text": f"{lead} | {row_label} | {cells}", "title": title,
                        "source_url": url, "fetched": date, "score": 0.0, "rerank": None})
    return results


def matching_titles(text: str, exclude=(), n: int = 4) -> str:
    """A short list of pages/documents whose *titles* match `text`, for the model to open.

    Passage search ranks paragraphs, so a page whose one relevant paragraph is
    outranked never shows up at all (the T&P page, EXPERIMENTS-LOG §16). Its
    title still matches. Listing a few titles costs ~60 tokens and lets the
    model see that the page exists and read_document it -- measured: without
    this list gpt-oss-20b kept re-reading the placement report it had already
    been shown instead of looking for another page.
    """
    sources = _catalogue()
    skip = set(exclude)
    lines = []
    for _, i in _title_scores(text):
        s = sources[i]
        if s["url"] in skip:
            continue
        date = f" (dated {s['date']})" if s["date"] and generate._is_document(s["url"]) else ""
        lines.append(f"S{i}: {s['title']}{date}")
        if len(lines) >= n:
            break
    return "Other pages and documents whose titles match (open with read_document):\n" + "\n".join(lines)


def _titles(results, n=3) -> str:
    seen = []
    for r in results:
        if r["title"] not in seen:
            seen.append(r["title"])
    return "; ".join(seen[:n]) if seen else "nothing found"
