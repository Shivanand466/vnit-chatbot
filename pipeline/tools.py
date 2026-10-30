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
import re

import generate
import query
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
        self.passages = []   # dicts: pid, result, text (as shown to the model)
        self._by_key = {}

    @staticmethod
    def _key(r):
        return (r["source_url"], r["text"][:80])

    def add(self, r: dict, text: str, origin: str = "tool"):
        """Register a passage; returns (pid, is_new). `origin` is "first" for the first search."""
        key = self._key(r)
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
        "name": "calculate",
        "description": "Exact arithmetic, e.g. '125000 * 4' or '32650 - 32150'. Use it for any "
                       "total, difference or multiplication in your answer.",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "An arithmetic expression."}},
            "required": ["expression"]}}},
]

TOOL_NAMES = [s["function"]["name"] for s in SCHEMAS]


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

        if name == "calculate":
            expr = str(args.get("expression", ""))
            value = safe_calculate(expr)
            return {"observation": f"{expr} = {value}", "summary": f"Calculated {expr} = {value}",
                    "value": value}

        return {"observation": f"Error: unknown tool {name!r}. Available: {', '.join(TOOL_NAMES)}.",
                "summary": f"Asked for an unknown tool ({name})"}
    except Exception as e:  # a tool must never take the whole answer down
        return {"observation": f"Error running {name}: {type(e).__name__}: {e}",
                "summary": f"{name} failed ({type(e).__name__})"}


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
