"""
Grade the first search before the agent answers from it (Corrective RAG).

Until this module, deciding whether the first search was good enough was left
entirely to the LLM. It usually judges well, but not always: for the 2025-26
placement figures it opened the placement *report* twice and never the T&P
page that states them (EXPERIMENTS-LOG §20c), although `read_document` finds
the figures there at rank 1. Corrective RAG grades the retrieved passages and
fixes the retrieval *before* answering when they look weak.

The grade is plain code, from two signals the search already produces:
- `top`: the cross-encoder's best score for the whole question. It reads the
  question and each passage together, so a low best score means nothing
  retrieved is really about the question. These scores used to be thrown away
  after sorting; query.py now keeps them.
- `coverage`: the share of the question's rarer words (and any academic year
  it names) that appear in the top three passages. A high score on a passage
  that misses the question's key word ("placed", "2025-26") is a near miss.

    correct     top >= HIGH and coverage >= COVER: answer from the first search
    incorrect   top < LOW: the first search found nothing relevant
    ambiguous   anything in between, and always when the question names an
                academic year that none of the top passages mention

The thresholds were chosen from measurements, not guessed: grade_calibration.py
prints top and coverage for every answerable question in check_answers.py,
alongside whether the answer passage was among those sent to the LLM. The
table and the reasoning are in EXPERIMENTS-LOG §22.
"""
import math
import statistics

import query
from programme_terms import years
from tools import _words

HIGH = 3.0
LOW = 0.0
COVER = 0.75

TOP_PASSAGES = 3

_df_cache = {"mtime": None, "idf": None}


def _idf():
    """How rare each word stem is across all chunks (log N / chunks containing it)."""
    data = query.load_index()
    if _df_cache["mtime"] != query._index_cache["mtime"]:
        df = {}
        for c in data["chunks"]:
            for w in _words(f"{c['title']} {c['text']}"):
                df[w] = df.get(w, 0) + 1
        n = len(data["chunks"])
        _df_cache["idf"] = {w: math.log(n / k) for w, k in df.items()}
        _df_cache["mtime"] = query._index_cache["mtime"]
    return _df_cache["idf"]


def whole_question_results(report: dict) -> list:
    """The results retrieved for the question as asked (not for one of its parts)."""
    if report.get("whole_question_results"):
        return report["whole_question_results"]
    parts = report.get("sub_questions") or []
    return parts[0]["results"] if parts else []


def key_words(question: str) -> list:
    """The question's rarer word stems: those at or above the median rarity of its words.

    A stem found in no chunk at all is left out: nothing could cover it.
    """
    idf = _idf()
    known = sorted((w for w in _words(question) if w in idf), key=lambda w: -idf[w])
    if not known:
        return []
    median = statistics.median(idf[w] for w in known)
    return [w for w in known if idf[w] >= median]


def grade(question: str, report: dict) -> dict:
    """Grade the first search: correct, ambiguous or incorrect, with the reason."""
    results = whole_question_results(report)
    scores = [r.get("rerank") for r in results if r.get("rerank") is not None]
    top = max(scores) if scores else None

    shown = results[:TOP_PASSAGES]
    seen_words = set()
    for r in shown:
        seen_words |= _words(f"{r['title']} {r['text']}")
    seen_years = set()
    for r in shown:
        seen_years |= years(f"{r['title']} {r['text']}")

    wanted = key_words(question)
    missing_years = [y for y in sorted(years(question)) if y not in seen_years]
    missing = [w for w in wanted if w not in seen_words] + missing_years
    total = len(wanted) + len(years(question))
    coverage = 1.0 if not total else (total - len(missing)) / total

    if top is None:
        # Without the reranker there is no score to judge by; leave the
        # decision to the planner, as before this module existed.
        return {"grade": "correct", "top": None, "coverage": coverage,
                "why": "no reranker scores to judge by"}
    if top < LOW:
        verdict, why = "incorrect", f"best match scored {top:.1f}, below {LOW:.0f}"
    elif missing_years:
        # The question names an academic year no top passage mentions: the
        # 2015-16 hostel fee question scored 5.1 on the 2026-27 fee sheets.
        verdict, why = "ambiguous", f"the top passages do not mention {', '.join(missing_years)}"
    elif top >= HIGH and coverage >= COVER:
        verdict, why = "correct", f"best match scored {top:.1f}"
    elif top < HIGH:
        verdict, why = "ambiguous", f"best match scored only {top:.1f}"
    else:
        verdict, why = "ambiguous", ("the top passages do not mention "
                                     + ", ".join(f"“{w}”" for w in missing))
    return {"grade": verdict, "top": top, "coverage": round(coverage, 2), "why": why}
