"""
Check a drafted answer against the passages it was written from.

The answering prompt already tells the model never to invent a figure. This
module checks that it didn't: every figure, date, email address and phone
number in the answer must appear in a passage the model was actually shown, be
the result of a `calculate` call, or be the visible result of a calculation
written out in the answer itself ("1,25,000 x 4 = 5,00,000"). Anything else is
reported as unsupported.

It is plain code, not a second LLM call, for three reasons:
- it costs nothing, which matters on a free tier capped at 8,000 tokens a
  minute;
- it is deterministic, so the same answer always gets the same verdict, and a
  test can pin that down (test_agentic.py);
- a model asked to grade its own answer tends to agree with itself.

What it cannot do: judge whether a *name* or a *sentence* is supported, or
whether a supported figure was attached to the right label. Figures are where
a wrong answer does the most harm (a fee, a deadline), and where checking is
exact, so that is what it checks. The verdict is shown in the chat page, so a
student can see what was and wasn't confirmed.
"""
import re

# A run of digit groups joined by hyphens or spaces, long enough to be a phone
# number ("1800-180-5522", "0712 2801 364"). Checked as one digit string,
# because sources and answers break phone numbers up differently.
_PHONE = re.compile(r"(?<![\d.])\d{2,5}(?:[ \-‐‑–]\d{2,5}){1,3}(?!\d|\.\d)")
_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# "2025-26", "2026–2027"; not an ISO date ("2026-04-10").
_ACADEMIC_YEAR = re.compile(r"(?<!\d)(20\d{2})\s*[-/]\s*(20\d{2}|\d{2})(?!\d|[-/]\d)")
_CITATION = re.compile(r"\[(?:P?\d+)(?:\s*,\s*P?\d+)*\]")
_LAKH = re.compile(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore)", re.I)
# A calculation written out in the answer: "125000 x 4 = 500000". The left
# side must start at a number, or in "Total = 125,000 x 4 = 500,000" the scan
# pairs "Total =" with 125,000 and skips past the real calculation.
_WORKED = re.compile(r"([\d(][\d,.\s()+\-*/x×÷₹]*?)\s*=\s*(?:Rs\.?|INR|₹)?\s*(\d[\d,]*(?:\.\d+)?)")

# Same wording check_answers.py uses for "the material doesn't say".
NOT_FOUND = re.compile(
    r"(do(es)? not|doesn't|don't|no (information|details|mention)|"
    r"not (contain|mention|provide|cover|include|specif|state|available|list)|couldn't find|"
    r"could not find|unable to find|none of the (provided |retrieved )?(passages|documents|sources)|"
    r"no (passage|document|source)s? (provides?|contains?|mentions?|states?|gives?))",
    re.I)

SMALL = 10  # numbers below this (counts, ordinals, list markers) are not checked


def _value(num: str):
    """A number as written ("1,25,000", "09", "1.50") -> canonical string ("125000", "9", "1.5")."""
    num = num.replace(",", "").rstrip(".")
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    return num.lstrip("0") or "0"


def _numbers(text: str) -> set:
    return {_value(m) for m in _NUMBER.findall(text)}


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _normalise(text: str) -> str:
    """Typographic dashes and spaces -> ASCII, ordinals glued ("19 th" -> "19th")."""
    text = re.sub(r"[‐‑‒–—−]", "-", text)
    text = re.sub(r"[   ]", " ", text)
    return re.sub(r"(\d)\s+(st|nd|rd|th)\b", r"\1\2", text, flags=re.I)


def is_refusal(answer: str) -> bool:
    # The model writes typographic apostrophes ("couldn’t find").
    return bool(NOT_FOUND.search(answer.replace("’", "'")))


def extract_claims(answer: str):
    """The checkable claims in `answer`: (kind, text-as-written, canonical value)."""
    text = _CITATION.sub(" ", _normalise(answer))
    claims = []
    for email in _EMAIL.findall(text):
        claims.append(("email", email, email.lower().rstrip(".")))
    text = _EMAIL.sub(" ", text)
    # An academic year is one claim, compared as "2026-27" however it is
    # written: checked number by number, "2026-27" against a source saying
    # "2026-2027" flagged "27" as invented (seen in the 2026-10-30 run).
    for m in list(_ACADEMIC_YEAR.finditer(text)):
        claims.append(("year", m.group(0), f"{m.group(1)}-{m.group(2)[-2:]}"))
    text = _ACADEMIC_YEAR.sub(" ", text)
    for phone in _PHONE.findall(text):
        digits = _digits(phone)
        if len(digits) >= 8:
            claims.append(("phone", phone, digits))
            text = text.replace(phone, " ", 1)
    for num in _NUMBER.findall(text):
        value = _value(num)
        try:
            if float(value) < SMALL:
                continue
        except ValueError:
            continue
        claims.append(("figure", num, value))
    return claims


def _derived(answer: str) -> set:
    """Results of calculations written out in the answer whose arithmetic checks out."""
    from tools import safe_calculate

    found = set()
    for left, right in _WORKED.findall(_normalise(answer)):
        left = left.strip()
        if not re.search(r"\d\s*[+\-*/x×÷]\s*\(?\s*\d", left):
            continue  # "Fee = 32150" restates a figure; it is not a calculation
        try:
            if abs(float(safe_calculate(left)) - float(_value(right))) < 0.01:
                found.add(_value(right))
        except Exception:
            continue
    return found


def verify(answer: str, passages, question: str = "", computed=()) -> dict:
    """Check every figure, email and phone number in `answer` against `passages`.

    `passages` are the texts the model was shown; `computed` are values returned
    by the calculate tool. Returns a dict with `verdict` ("verified", "refused",
    "unsupported" or "nothing to check"), the counts, and the unsupported claims.
    """
    evidence = _normalise("\n".join(passages))
    evidence_numbers = _numbers(evidence)
    evidence_digits = _digits(evidence)
    evidence_low = evidence.lower()
    # "1.5 lakh" in an answer may be "1,50,000" in the source, and the reverse.
    for amount, unit in _LAKH.findall(evidence):
        evidence_numbers.add(_value(str(round(float(amount) * (10 ** 7 if unit.lower() == "crore" else 10 ** 5)))))
    allowed = (_numbers(_normalise(question)) | {_value(str(c)) for c in computed}
               | _derived(answer))

    evidence_years = {f"{a}-{b[-2:]}" for a, b in _ACADEMIC_YEAR.findall(evidence)}
    question_years = {f"{a}-{b[-2:]}" for a, b in _ACADEMIC_YEAR.findall(_normalise(question))}

    claims = extract_claims(answer)
    unsupported = []
    for kind, written, value in claims:
        if kind == "email":
            ok = value in evidence_low
        elif kind == "year":
            ok = value in evidence_years or value in question_years
        elif kind == "phone":
            ok = value in evidence_digits
        else:
            ok = value in evidence_numbers or value in allowed
            if not ok:
                lakh = _LAKH.search(answer[answer.find(written):answer.find(written) + len(written) + 8])
                if lakh:
                    scale = 10 ** 7 if lakh.group(2).lower() == "crore" else 10 ** 5
                    ok = _value(str(round(float(value) * scale))) in evidence_numbers
            # Long figures may be written with different grouping in the source.
            if not ok and len(value.replace(".", "")) >= 6:
                ok = value.replace(".", "") in evidence_digits
        if not ok:
            unsupported.append(written.strip())

    if unsupported:
        verdict = "unsupported"
    elif is_refusal(answer) and not claims:
        verdict = "refused"
    elif not claims:
        verdict = "nothing to check"
    else:
        verdict = "verified"
    return {"verdict": verdict, "checked": len(claims),
            "supported": len(claims) - len(unsupported),
            "unsupported": sorted(set(unsupported), key=unsupported.index)}


def summary(result: dict) -> str:
    """One line for the chat page's trace."""
    v = result["verdict"]
    if v == "verified":
        return f"Checked {result['checked']} figure(s) against the sources: all found."
    if v == "unsupported":
        return (f"Checked {result['checked']} figure(s): could not find "
                f"{', '.join(result['unsupported'])} in the sources.")
    if v == "refused":
        return "The sources do not cover this, so the answer says so instead of guessing."
    return "No figures, dates or contact details to check in this answer."
