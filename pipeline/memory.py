"""
The conversation the assistant remembers, trimmed to what the free tier can afford.

v1 sent only the earlier *questions*, the last three, and used them for one
thing: rewriting a follow-up like "and for girls?". It never knew what it had
answered, so "how do I pay it?" after a fee answer, or "summarise what you
told me", had nothing to go on. Claude and ChatGPT remember the whole
exchange; here the chat page sends the earlier questions *and answers*
(`turns`), and this module keeps a bounded slice of them:

- the last MAX_TURNS turns, oldest dropped first;
- each answer cut to ANSWER_CHARS, without its source list, citation numbers
  or "Who can help" footer (they cost tokens and say nothing new);
- the whole block within MAX_TOKENS, dropping the oldest turns until it fits.

Earlier answers are context, never evidence. They are shown to the agent so it
understands the conversation, but they are not passages: the verifier checks
figures only against passages found in this turn, so a figure the assistant
said earlier must be found (and cited) again before it is repeated. Nothing
here is stored on the server.
"""
import re

MAX_TURNS = 6
ANSWER_CHARS = 600
QUESTION_CHARS = 500
MAX_TOKENS = 1500
CHARS_PER_TOKEN = 3.0   # the same rough rate planner._estimate_tokens uses

_CITATION_NUMBERS = re.compile(r"\s*\[\d+\]")
_FOOTERS = re.compile(r"\n+\s*(\*\*Who can help:\*\*|Note: I could not confirm|Sources?:).*", re.S)


def _clean_answer(text: str) -> str:
    text = _FOOTERS.sub("", text or "")
    text = _CITATION_NUMBERS.sub("", text).strip()
    if len(text) > ANSWER_CHARS:
        text = text[:ANSWER_CHARS].rsplit(" ", 1)[0] + "..."
    return text


def clean_turns(turns) -> list:
    """The turns worth remembering, as [{"q": ..., "a": ...}], newest last.

    Accepts what a browser may send: dicts with "q"/"a" (or "question"/"answer"),
    skipping anything malformed rather than failing the question.
    """
    kept = []
    for t in turns or []:
        if not isinstance(t, dict):
            continue
        q = str(t.get("q") or t.get("question") or "").strip()[:QUESTION_CHARS]
        a = _clean_answer(str(t.get("a") or t.get("answer") or ""))
        if q:
            kept.append({"q": q, "a": a})
    kept = kept[-MAX_TURNS:]
    while kept and _tokens(kept) > MAX_TOKENS:
        kept = kept[1:]
    return kept


def _tokens(turns) -> int:
    return int(len(block(turns)) / CHARS_PER_TOKEN)


def block(turns) -> str:
    """The turns as a short text block for a prompt ("" when there are none)."""
    if not turns:
        return ""
    lines = []
    for t in turns:
        lines.append(f"Student: {t['q']}")
        if t["a"]:
            lines.append(f"Assistant: {t['a']}")
    return "\n".join(lines)


def questions(turns) -> list:
    """Just the questions, in v1's `history` form."""
    return [t["q"] for t in turns]


def prompt_block(turns) -> str:
    """The "Conversation so far" block the agent's first message carries."""
    text = block(turns)
    if not text:
        return ""
    return ("Conversation so far (context only, not a source: any VNIT figure, date or contact "
            "you repeat from it must be found again in a passage and cited):\n" + text + "\n\n")
