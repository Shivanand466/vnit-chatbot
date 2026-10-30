"""
One entry point for answering a message, and the place the hierarchy lives.

    respond.answer(question, history)

      1. RESOLVE   followup.resolve -- "and for girls?" becomes a question that
                   stands on its own, because retrieval has no memory.
      2. ROUTE     router.route -- what kind of message is this?
      3. SEARCH    only a lookup searches: agent.answer decomposes the question,
                   retrieves per part and for the whole.
      4. PLAN/ACT  planner.run hands those passages to the agent, which decides
                   whether they answer the question or whether to act: search
                   again, open a specific document, calculate.
      5. VERIFY    every figure in the answer is checked against the passages
                   shown (verifier.py), and fixed or flagged if unsupported.
      The other kinds get a short direct reply with no passages at all.

If the agent cannot run (no key, quota spent, network), step 4 falls back to
the one-shot composer (generate.llm_answer) on the same passages, which itself
falls back to quoting passages -- and the answer is still verified, because
the check needs no LLM. AGENT_MODE=off forces the one-shot path, which is how
check_answers.py compares the two.

Everything that answers a user -- the API and check_answers.py -- goes through
here, so the tests exercise the same path as the chat page. Before this
existed, `api/main.py` called retrieval directly and a greeting triggered a
full search of 8,000 passages, while "what can you do?" was answered out of
whichever documents came back.
"""
import os

import agent
import followup
import generate
import planner
import router
import tools
import verifier

# What the chatbot covers, used for the capability and out-of-scope replies.
# Written here rather than in the prompt so these answers are identical every
# time and cost nothing.
SCOPE = [
    "admissions and reporting instructions",
    "fees (tuition, hostel, mess) and fee remission",
    "hostels and their rules",
    "scholarships and their deadlines",
    "academic calendars, exam schedules and course registration",
    "placements and internships",
    "departments, their programmes and specialisations",
    "the administration (Director, Registrar, Deans) and contact details",
]

CAPABILITY_ANSWER = (
    "I answer questions about **VNIT Nagpur** using only the institute's own "
    "website and the documents it publishes, and I show you the source of every "
    "answer.\n\n"
    "I can help with:\n"
    + "\n".join(f"- {item}" for item in SCOPE)
    + "\n\nTry asking something specific, for example *\"What is the hostel fee for "
    "first year B.Tech boys for Winter 2026?\"* You can also ask a follow-up like "
    "*\"and for girls?\"* and I will understand it.\n\n"
    "If something isn't in VNIT's material, I say so rather than guessing."
)

GREETING_ANSWER = (
    "Hello! I'm the VNIT Nagpur chatbot. Ask me about admissions, fees, hostels, "
    "scholarships, exams, placements or departments, and I'll answer from VNIT's "
    "own website and documents with a link to the source.\n\n"
    "What would you like to know?"
)

THANKS_ANSWER = "You're welcome. Ask me anything else about VNIT whenever you need to."

OUT_OF_SCOPE_ANSWER = (
    "That one is outside what I can help with: I only answer from VNIT Nagpur's "
    "website and documents, so I can't help with general knowledge, other "
    "institutes, or writing and homework tasks.\n\n"
    "I can answer things like:\n"
    + "\n".join(f"- {item}" for item in SCOPE[:5])
)

DIRECT_ANSWERS = {
    router.GREETING: GREETING_ANSWER,
    router.THANKS: THANKS_ANSWER,
    router.CAPABILITY: CAPABILITY_ANSWER,
    router.OUT_OF_SCOPE: OUT_OF_SCOPE_ANSWER,
}


def warm_up():
    """Load the index, the search models and the document titles, without any LLM call.

    The server runs this before taking requests, so the first student isn't
    the one who waits ~20s for models to load -- and a restart costs none of
    the free LLM quota.
    """
    agent.answer("warm up the search index")
    tools.run_tool("find_documents", {"keywords": "academic calendar"}, tools.Evidence())


def agent_enabled() -> bool:
    return os.environ.get("AGENT_MODE", "on").strip().lower() not in ("off", "0", "false", "no")


def answer(question: str, history=None, k: int = 7, use_agent: bool = None) -> dict:
    """Answer one message. Returns answer, sources, mode, trace, and how it was handled.

    `mode` says which path ran: "agent (model)" for the planner, "llm (model)"
    for the one-shot composer, "extractive (reason)" when no LLM could be used,
    and "direct (<kind>)" when no search was needed. `trace` lists the steps
    taken, for the chat page's "How I found this".
    """
    use_agent = agent_enabled() if use_agent is None else use_agent
    asked = (question or "").strip()
    searched, rewrite_note = followup.resolve(asked, history or [])
    kind = router.route(searched)

    trace = []
    if rewrite_note:
        trace.append({"step": "understand",
                      "text": f"Read the follow-up with the earlier questions as: “{searched}”"})
    trace.append({"step": "route", "text": ROUTE_NOTES[kind]})

    if kind in router.NO_SEARCH:
        return {
            "question": asked,
            "understood_as": searched if rewrite_note else None,
            "answer": DIRECT_ANSWERS[kind],
            "sources": [],
            "mode": f"direct ({kind})",
            "kind": kind,
            "sub_questions": [],
            "trace": trace,
            "verification": None,
        }

    report = agent.answer(searched, k=k)
    sub_questions = [sq["sub_question"] for sq in report["sub_questions"]]
    search_note = {"step": "search", "text": "Searched VNIT's pages and documents"
                   + (f" in {len(sub_questions)} parts" if len(sub_questions) > 1 else "") + "."}

    if use_agent:
        try:
            result = planner.run(searched, report)
            return {
                "question": asked,
                "understood_as": searched if rewrite_note else None,
                "answer": result["answer"],
                "sources": result["sources"],
                "mode": result["mode"],
                "kind": kind,
                "sub_questions": sub_questions,
                "trace": trace + result["trace"],
                "verification": result["verification"],
                "usage": result["usage"],
            }
        except Exception as e:
            trace.append(search_note)
            trace.append({"step": "fallback",
                          "text": f"The agent could not run ({_short(e)}), so the answer was "
                                  "written in one step from the first search."})
            # The usual reason is a spent per-minute allowance; the one-shot
            # prompt (~2,500 tokens) would be refused too without a short wait.
            planner.wait_for_quota(FALLBACK_TOKENS)
    else:
        trace.append(search_note)

    composed = generate.llm_answer(report)
    # The check needs no LLM, so the one-shot and quoted answers are verified too.
    shown = [f"{generate.passage_header(r)} {text}" for r, text in generate.select_passages(report)]
    check = None
    if composed["mode"].startswith("llm"):
        check = verifier.verify(composed["answer"], shown, searched)
        trace.append({"step": "verify", "text": verifier.summary(check), "verdict": check["verdict"]})
    return {
        "question": asked,
        "understood_as": searched if rewrite_note else None,
        "answer": composed["answer"],
        "sources": composed["sources"],
        "mode": composed["mode"],
        "kind": kind,
        "sub_questions": sub_questions,
        "trace": trace,
        "verification": check,
    }


FALLBACK_TOKENS = 3000

ROUTE_NOTES = {
    router.GREETING: "Recognised a greeting, so no search was needed.",
    router.THANKS: "Recognised a thank-you, so no search was needed.",
    router.CAPABILITY: "Recognised a question about what I can do, so no search was needed.",
    router.OUT_OF_SCOPE: "Recognised a question outside VNIT's material, so I did not search.",
    router.LOOKUP: "A question about VNIT: looking it up.",
}


def _short(e: Exception) -> str:
    text = str(e) or type(e).__name__
    # Never echo anything key-like back to a user.
    if "Bearer" in text or "gsk_" in text:
        return type(e).__name__
    return text[:120]
