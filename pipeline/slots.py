"""
Ask the student which group they mean, or remember it from earlier in the chat.

"What is the hostel fee?" has no single answer: VNIT publishes 19 near-identical
hostel fee sheets, one per programme, year and gender, and the first search
returns several of them. Before this module the agent picked one and answered
for that group, so a girl could be told the boys' fee. AdvisingWise's agent can
ask the student for missing information and keeps a student profile; MARAUS
found most of its remaining errors came from vague questions. This does both,
in plain code:

- `extract` reads the details a question gives: programme, gender, category
  (OPEN, OBC, SC/ST, ...) and year of study;
- `needs_clarification` asks back only when a detail the topic needs is
  missing *and* the passages found hold two or more different values for it,
  i.e. when the answer really depends on it. "Who is the Director?" never
  needs a programme, and a question whose passages all concern B.Tech is just
  answered;
- `apply_profile` fills a detail the student gave earlier ("Girls", from a
  button) into a later question, and says so in the trace.

The profile lives in the chat page and is sent with each question; the server
never stores it. `clean_profile` keeps only known keys and values, so a crafted
request cannot slip text into the question through it.
"""
import re

from programme_terms import genders, programmes

PROFILE_KEYS = ("programme", "gender", "category", "study_year")

REQUIRED = {"hostel": ["programme", "gender"], "fees": ["programme", "category"],
            "calendar": ["programme"]}

LABELS = {
    "programme": {"btech": "B.Tech", "barch": "B.Arch", "mtech": "M.Tech", "msc": "M.Sc",
                  "mba": "MBA", "phd": "Ph.D"},
    "gender": {"boys": "Boys", "girls": "Girls"},
    "category": {"open": "OPEN / General", "obc": "OBC", "sc/st": "SC/ST", "sc": "SC",
                 "st": "ST", "ews": "EWS", "pwd": "PwD"},
    "study_year": {"first": "First year", "second": "Second year", "third": "Third year",
                   "fourth": "Fourth year", "final": "Final year"},
}

QUESTIONS = {
    "programme": "Which programme are you asking about?",
    "gender": "Is this for boys or girls?",
    "category": "Which admission category are you in?",
    "study_year": "Which year of study are you in?",
}

# Category names as the fee sheets write them. SC, ST and OPEN are matched in
# capitals only: "St." and "open" are ordinary words, and "M.SC" is a programme.
_CATEGORIES = [
    ("sc/st", re.compile(r"\bSC\s*/\s*ST\b", re.I)),
    ("obc", re.compile(r"\bOBC", re.I)),
    ("ews", re.compile(r"\bEWS\b", re.I)),
    ("pwd", re.compile(r"\bPwD\b|\bPWD\b|persons? with disabilit", re.I)),
    ("open", re.compile(r"\bOPEN\b|\bGEN\b")),
    ("sc", re.compile(r"(?<![./\w])SC\b(?!\s*/)")),
    ("st", re.compile(r"(?<![/\w])ST\b")),
]
_OPEN_WORDS = re.compile(r"\b(?:open|general)\s+category\b", re.I)

_STUDY_YEAR = [
    ("first", r"\b(first|1st|i)\s+year\b"),
    ("second", r"\b(second|2nd|ii)\s+year\b"),
    ("third", r"\b(third|3rd|iii)\s+year\b"),
    ("fourth", r"\b(fourth|4th|iv)\s+year\b"),
    ("final", r"\b(final|last)\s+year\b"),
]


def categories(text: str) -> set:
    found = {name for name, pattern in _CATEGORIES if pattern.search(text)}
    if _OPEN_WORDS.search(text):
        found.add("open")
    if "sc/st" in found:
        found -= {"sc", "st"}
    return found


def study_years(text: str) -> set:
    return {name for name, pattern in _STUDY_YEAR if re.search(pattern, text, re.I)}


_READERS = {"programme": programmes, "gender": genders, "category": categories,
            "study_year": study_years}


def extract(text: str) -> dict:
    """The details `text` states, each only when it names exactly one value."""
    found = {}
    for slot, reader in _READERS.items():
        values = reader(text or "")
        if len(values) == 1:
            found[slot] = next(iter(values))
    return found


def clean_profile(profile) -> dict:
    """Keep only known slots with known values; anything else is dropped."""
    if not isinstance(profile, dict):
        return {}
    return {k: v for k, v in profile.items()
            if k in PROFILE_KEYS and isinstance(v, str) and v in LABELS[k]}


def needs_clarification(question: str, intent: str, passages, profile=None):
    """A clarifying question with 2-4 choices, or None to just answer.

    `passages` are the first search's results (dicts with title, text and the
    reranker's score). A slot is asked about only when the topic needs it,
    neither the question nor the profile gives it, and the *relevant* passages
    (rerank >= RELEVANT) hold two or more different values for it. A passage
    naming several values at once ("Boys & Girls", "OPEN / OBC / EWS") is a
    general one and does not count.

    The relevance floor is what keeps the existing questions from being asked
    back: "How much does one summer term course cost?" found M.Tech and B.Arch
    fee estimates, but at scores of 2-3 -- they were not about the question, so
    they say nothing about which programme it needs.
    """
    profile = clean_profile(profile or {})
    given = extract(question)
    relevant = [r for r in passages if r.get("rerank") is not None and r["rerank"] >= RELEVANT]
    for slot in REQUIRED.get(intent, []):
        if slot in given or slot in profile or _READERS[slot](question):
            continue
        documents = {}
        for r in relevant:
            values = _READERS[slot](f"{r['title']} {r['text']}")
            if len(values) == 1:
                documents.setdefault(next(iter(values)), set()).add(r["source_url"])
        if len(documents) >= 2:
            return {"slot": slot, "question": QUESTIONS[slot],
                    "choices": _choices(slot, question, documents)}
    return None


# Rerank score from which a passage counts as being about the question; the
# same line grader.py draws between a good first search and a doubtful one.
RELEVANT = 3.0
TITLES_CONSULTED = 10


def _choices(slot: str, question: str, documents: dict) -> list:
    """Up to 4 choices: the values most documents fit, shown in a fixed order.

    The best-titled documents are counted too, because a programme is often
    named only in a title, and often as a pair ("UG (B.Tech/B.Arch)"): the 19
    hostel fee sheets rarely say "B.Tech" in their passages. Which values are
    offered depends on the counts; the order they are shown in does not, so
    the B.Tech button is always first when it is offered.
    """
    import query
    import tools

    documents = {v: set(urls) for v, urls in documents.items()}
    catalogue = query.list_sources()
    for _score, i in tools._title_scores(question)[:TITLES_CONSULTED]:
        values = _READERS[slot](catalogue[i]["title"])
        if 1 <= len(values) <= 2:
            for v in values:
                documents.setdefault(v, set()).add(catalogue[i]["url"])
    order = list(LABELS[slot])
    kept = sorted(documents, key=lambda v: (-len(documents[v]), order.index(v)))[:4]
    return [{"label": LABELS[slot][v], "value": v} for v in sorted(kept, key=order.index)]


def describe(profile: dict) -> str:
    """"B.Tech girls, OPEN / General category" for the slots in `profile`."""
    parts = []
    if "study_year" in profile:
        parts.append(LABELS["study_year"][profile["study_year"]].lower())
    if "programme" in profile:
        parts.append(LABELS["programme"][profile["programme"]])
    if "gender" in profile:
        parts.append(profile["gender"])
    text = " ".join(parts)
    if "category" in profile:
        text += (", " if text else "") + f"{LABELS['category'][profile['category']]} category"
    return text


def apply_profile(question: str, intent: str, profile=None):
    """Add the profile's details the question lacks and its topic needs.

    Returns (question, note); the note is None when nothing was added.
    "What is the hostel fee? (for B.Tech girls)", "Assuming B.Tech girls, from
    earlier in this chat."
    """
    profile = clean_profile(profile or {})
    given = extract(question)
    fill = {slot: profile[slot] for slot in REQUIRED.get(intent, [])
            if slot in profile and slot not in given and not _READERS[slot](question)}
    if not fill:
        return question, None
    words = describe(fill)
    return f"{question} (for {words})", f"Assuming {words}, from earlier in this chat."
