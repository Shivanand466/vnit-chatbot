"""
Make a follow-up question stand on its own before it is searched for.

Retrieval has no memory: each question is embedded and matched by itself. So a
perfectly natural exchange fails --

    "What is the hostel fee for first year B.Tech boys for Winter 2026?"  -> correct
    "and for girls?"                                                     -> nonsense

because "and for girls?" matches no passage in particular. This module spots a
question that cannot stand alone and rewrites it using the previous questions,
so what reaches `agent.answer` is "What is the hostel fee for first year
B.Tech girls for Winter 2026?".

Two ways of rewriting, in order:
  1. the LLM, asked only to rewrite (a short prompt, a few dozen tokens) --
     this is the standard "condense question" step of a conversational RAG;
  2. if there is no key or the call fails, glue the previous question and the
     follow-up together. The result reads awkwardly, but retrieval only needs
     the words to be present, and it never leaves the user with nonsense.

The rewritten question is returned to the caller so the chat page can show
"Understood as: ...". Guessing what someone meant is only acceptable if they
can see the guess.
"""
import os
import re

# Only ever rewrite a question that plainly cannot stand alone, so an ordinary
# question is never altered (and never costs an extra LLM call).
MAX_FOLLOWUP_WORDS = 12

# "and for girls?", "what about M.Tech?", "how about second year?", "for PG?"
_CONNECTIVE_START = re.compile(
    r"^(and|also|but|so)\b|^(what|how)\s+about\b|^(and\s+)?(for|in|at|on)\b", re.IGNORECASE
)
# "when is it?", "who signs that?", "how much do they pay?" -- a referring word
# with no subject of its own.
_BARE_REFERENCE = re.compile(r"\b(it|its|this|that|these|those|they|them|their|there|same)\b",
                             re.IGNORECASE)
# A question carrying its own subject does not need history, even if short.
_HAS_SUBJECT = re.compile(
    r"\b(vnit|fee|fees|hostel|scholarship|exam|exams|calendar|admission|placement|director|"
    r"registrar|dean|library|department|b\.?tech|m\.?tech|b\.?arch|phd|mba|course|semester)\b",
    re.IGNORECASE,
)


def looks_like_followup(question: str) -> bool:
    """True when `question` needs earlier context to make sense on its own."""
    q = question.strip().rstrip("?").strip()
    if not q or len(q.split()) > MAX_FOLLOWUP_WORDS:
        return False
    if _CONNECTIVE_START.search(q):
        return True
    # A bare referring word is only a follow-up if the question says nothing
    # concrete itself: "is it free?" yes, "is the hostel fee the same?" no.
    return bool(_BARE_REFERENCE.search(q)) and not _HAS_SUBJECT.search(q)


def _glue(question: str, previous: str) -> str:
    """Fallback rewrite: keep both questions' words in one string."""
    core = re.sub(r"^(and|also|but|so)\b[\s,]*", "", question.strip(), flags=re.IGNORECASE)
    core = re.sub(r"^(what|how)\s+about\b[\s,]*", "", core, flags=re.IGNORECASE).strip(" ?")
    previous = previous.strip().rstrip("?")
    return f"{previous} - {core}" if core else previous


# gpt-oss-20b is a reasoning model: it spends its token budget on a separate
# reasoning channel and returns empty `content` if that budget runs out first.
# Measured on this rewrite prompt: max_tokens=80 and 400 both returned "" after
# 400 reasoning tokens; with reasoning_effort="low" it answered in 117 tokens.
# The parameter is Groq/gpt-oss specific, so a provider that rejects it gets a
# second attempt without it.
REWRITE_MAX_TOKENS = 400


def _llm_rewrite(question: str, history, api_key: str, base_url: str, model: str) -> str:
    import requests

    recent = "\n".join(f"- {h}" for h in history[-3:])
    prompt = (
        "Rewrite the student's latest question so that it can be understood on its own, "
        "using their earlier questions for context. Keep it in the student's words, change "
        "as little as possible, and do not answer it. Reply with the rewritten question and "
        "nothing else.\n\n"
        f"Earlier questions:\n{recent}\n\nLatest question: {question}\n\nRewritten question:"
    )
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": REWRITE_MAX_TOKENS, "temperature": 0, "reasoning_effort": "low"}

    def call(payload):
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        return (resp.json()["choices"][0]["message"].get("content") or "").strip().strip('"')

    try:
        rewritten = call(body)
    except Exception:
        rewritten = call({k: v for k, v in body.items() if k != "reasoning_effort"})
    # Guard against a chatty model: an answer, a refusal or an empty string
    # would be worse than the glued version, so sanity-check the shape.
    if not rewritten or len(rewritten.split()) > 40 or "\n" in rewritten.strip():
        raise ValueError(f"unusable rewrite: {rewritten[:80]!r}")
    return rewritten


def resolve(question: str, history, api_key: str = None, base_url: str = None,
            model: str = None) -> tuple:
    """Return (question_to_search, note).

    `note` is None when the question was left alone, otherwise a short string
    saying how it was read, for the chat page to show.
    """
    history = [h for h in (history or []) if h and h.strip()]
    if not history or not looks_like_followup(question):
        return question, None

    api_key = api_key or os.environ.get("GENAI_API_KEY")
    base_url = base_url or os.environ.get("GENAI_BASE_URL", "https://api.groq.com/openai/v1")
    model = model or os.environ.get("GENAI_MODEL", "openai/gpt-oss-20b")

    if api_key:
        try:
            return _llm_rewrite(question, history, api_key, base_url, model), "rewritten"
        except Exception:
            pass  # fall through to the glue fallback; never fail the question
    return _glue(question, history[-1]), "combined with your previous question"
