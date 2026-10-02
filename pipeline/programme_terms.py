"""
Which degree programme and which academic year a question or a passage is
about, so that candidates contradicting the question can be set aside before
reranking (query.py `_candidates`).

Why this exists: VNIT publishes near-identical documents per programme and per
year -- 19 hostel fee sheets differing only in programme, year and gender, a
dozen academic calendars, a placement report per year. Retrieval mixed them
up, the main weak spot recorded in README.md. Keyword search cannot help with
the programme, because scikit-learn's default tokenizer keeps only runs of two
or more word characters, so `B.Tech`, `B. Tech.` and `M.Tech` all collapse to
`tech`.

An earlier attempt appended tags like `btech` to the indexed text and to the
question; it diluted TF-IDF and measured worse (EXPERIMENTS-LOG.md §10). This
module is used differently: it only decides which candidates compete, never
how anything is scored, so it cannot dilute the ranking.
"""
import re

# tag -> pattern, matched case-insensitively.
_PATTERNS = {
    "btech": r"b\.?\s*tech|bachelor\s+of\s+technology",
    "barch": r"b\.?\s*arch|bachelor\s+of\s+architecture",
    "mtech": r"m\.?\s*tech|master\s+of\s+technology",
    "msc": r"m\.?\s*sc\b|master\s+of\s+science",
    "mba": r"\bmba\b|master\s+of\s+business",
    "phd": r"ph\.?\s*d\b|doctor\s+of\s+philosophy",
}

# "UG"/"PG" name a level rather than one programme, so they stand for every
# programme at that level: a question about UG fees must still match a document
# that only ever says "B.Tech".
_LEVELS = {
    "ug": (r"\bug\b|under[\s-]?graduate", {"btech", "barch"}),
    "pg": (r"\bpg\b|post[\s-]?graduate", {"mtech", "msc", "mba", "phd"}),
}

# Academic years as VNIT writes them: 2025-26, 2025–2026, 2025/26. A bare
# "2026" is deliberately not matched -- documents mention many bare years in
# passing (deadlines, past sessions), and treating those as the document's
# subject would set aside good candidates.
_ACADEMIC_YEAR = re.compile(r"\b(20\d{2})\s*[-–/]\s*(20\d{2}|\d{2})\b")


def programmes(text: str) -> set:
    """The programmes `text` mentions, as a set of tags. Empty when it names none."""
    low = text.lower()
    found = {tag for tag, pattern in _PATTERNS.items() if re.search(pattern, low)}
    for pattern, members in _LEVELS.values():
        if re.search(pattern, low):
            found |= members
    return found


def years(text: str) -> set:
    """The academic years `text` mentions, normalised to "2025-26"."""
    found = set()
    for start, end in _ACADEMIC_YEAR.findall(text):
        found.add(f"{start}-{end[-2:]}")
    return found


def contradicts(question: str, text: str) -> bool:
    """True when `text` is clearly about other programmes or other academic
    years than the question asks about.

    Only a text that states the attribute at all can contradict: a general fee
    page naming no programme stays eligible, which matters because many correct
    answers come from pages that never spell one out.
    """
    for reader in (programmes, years):
        asked = reader(question)
        if not asked:
            continue
        found = reader(text)
        if found and found.isdisjoint(asked):
            return True
    return False
