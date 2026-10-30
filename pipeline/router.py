"""
Decide what kind of question this is, before any searching happens.

The fault this fixes: every message went straight to retrieval, and the
answering prompt says "use ONLY these passages". So "what can you do?" was
answered out of a *Letter to Parents* about campus health facilities, because
the model was ordered to answer from whatever paragraphs came back. A greeting
cost a full search of 8,000 passages for nothing.

The hierarchy is plan -> act -> compose:

    route(question)              <- this module: what kind of question is it?
      |- GREETING / THANKS       -> answer straight away, no search
      |- CAPABILITY              -> describe what the chatbot covers
      |- OUT_OF_SCOPE            -> say what it is for, no invented answer
      `- LOOKUP                  -> search VNIT's pages and documents (agent.py)
                                    then compose with citations (generate.py)

Routing is heuristic first, because the obvious cases are obvious and should
not cost an API call or a second of waiting. Anything not obviously
conversational goes to LOOKUP: when in doubt, search -- an unnecessary search
wastes a moment, while a wrongly skipped one loses a real answer.
"""
import re

GREETING = "greeting"
THANKS = "thanks"
CAPABILITY = "capability"
OUT_OF_SCOPE = "out_of_scope"
LOOKUP = "lookup"

# Kinds that are answered without searching at all.
NO_SEARCH = (GREETING, THANKS, CAPABILITY, OUT_OF_SCOPE)

_GREETING = re.compile(
    r"^\s*(hi|hey|hello+|yo|hii+|namaste|good\s+(morning|afternoon|evening)|"
    r"how\s+are\s+you|what'?s\s+up|who\s+are\s+you|introduce\s+yourself)"
    r"[\s!.,?]*$", re.I)

_THANKS = re.compile(
    r"^\s*(thanks?|thank\s+you|thx|ty|great|cool|nice|ok(ay)?|got\s+it|"
    r"perfect|awesome|bye|goodbye|see\s+you)[\s!.,]*$", re.I)

# "what can you do", "what do you know", "how do you work", "can you help me"
_CAPABILITY = re.compile(
    r"\b(what|which)\s+(can|could)\s+you\s+(do|answer|help|tell)\b|"
    r"\bwhat\s+(do|can)\s+you\s+know\b|"
    r"\bwhat\s+(kind|sort|type)s?\s+of\s+(question|thing)s?\b|"
    r"\bhow\s+do\s+you\s+work\b|\bwhat\s+are\s+you\b|"
    r"\bcan\s+you\s+help\b|\bwhat\s+is\s+this\s+(bot|chatbot|site)\b|"
    r"\bwho\s+(made|built|created)\s+you\b", re.I)

# Things the chatbot has no business answering from VNIT's website: general
# knowledge, homework, other institutes, and anything asking it to write or
# compute something unrelated. Kept narrow on purpose -- this only fires when
# the question also says nothing about VNIT (see _VNIT_TERMS).
_OUT_OF_SCOPE = re.compile(
    r"\b(write|compose|draft|generate)\s+(me\s+)?(a|an|some)\s+"
    r"(poem|song|story|essay|code|program|script|email|letter)\b|"
    r"\b(prime\s+minister|president|capital\s+of|population\s+of|weather|"
    r"cricket\s+score|stock\s+price|bitcoin)\b|"
    r"\b(solve|integrate|differentiate)\s+(this|the\s+following)\b|"
    r"\bwho\s+is\s+(the\s+)?(ceo|founder)\s+of\b|"
    r"\b(iit|nit)\s+(bombay|delhi|madras|kanpur|kharagpur|trichy|warangal|surathkal)\b",
    re.I)

# If any of these appear, the question is about VNIT and belongs in LOOKUP even
# if it also looks like small talk or general knowledge.
_VNIT_TERMS = re.compile(
    r"\b(vnit|visvesvaraya|nagpur|hostel|mess|fee|fees|tuition|scholarship|"
    r"admission|exam|exams|examination|semester|calendar|convocation|placement|"
    r"internship|department|dept|faculty|professor|director|registrar|dean|"
    r"library|campus|course|courses|credit|credits|registration|cgpa|grade|"
    r"b\.?tech|m\.?tech|b\.?arch|m\.?sc|mba|ph\.?d|branch|intake|ragging|"
    r"warden|notice|timetable|time\s*table|slot|holiday|instruction\s+day)\b",
    re.I)


def route(question: str) -> str:
    """Which kind of question this is: one of the constants above."""
    q = (question or "").strip()
    if not q:
        return GREETING

    about_vnit = bool(_VNIT_TERMS.search(q))

    # A question naming anything VNIT-ish is a lookup, whatever else it says.
    if about_vnit:
        return LOOKUP
    if _GREETING.match(q):
        return GREETING
    if _THANKS.match(q):
        return THANKS
    if _CAPABILITY.search(q):
        return CAPABILITY
    if _OUT_OF_SCOPE.search(q):
        return OUT_OF_SCOPE
    return LOOKUP
