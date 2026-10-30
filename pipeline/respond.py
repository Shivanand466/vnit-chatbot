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
import json
import os
from pathlib import Path

import agent
import followup
import generate
import grader
import planner
import router
import slots
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


def answer(question: str, history=None, k: int = 7, use_agent: bool = None,
           profile: dict = None) -> dict:
    """Answer one message. Returns answer, sources, mode, trace, and how it was handled.

    `mode` says which path ran: "agent (model)" for the planner, "llm (model)"
    for the one-shot composer, "extractive (reason)" when no LLM could be used,
    and "direct (<kind>)" when no search was needed, and "clarify" when the
    question fits several groups' documents and the student is asked which one
    they mean (`clarify` then holds the choices). `trace` lists the steps
    taken, for the chat page's "How I found this".

    `profile` holds what the student told the chat page earlier (programme,
    gender, category, year of study; see slots.py). It fills in what a
    question leaves out, and is never stored.
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
    topic = None if kind in router.NO_SEARCH else router.intent(searched)
    if topic:
        trace.append({"step": "route", "text": f"Topic: {topic}."})
        searched, profile_note = slots.apply_profile(searched, topic, profile)
        if profile_note:
            rewrite_note = True
            trace.append({"step": "understand", "text": profile_note})

    if kind in router.NO_SEARCH:
        return {
            "question": asked,
            "understood_as": searched if rewrite_note else None,
            "answer": DIRECT_ANSWERS[kind],
            "sources": [],
            "mode": f"direct ({kind})",
            "kind": kind,
            "intent": topic,
            "sub_questions": [],
            "trace": trace,
            "verification": None,
        }

    report = agent.answer(searched, k=k)
    sub_questions = [sq["sub_question"] for sq in report["sub_questions"]]
    search_note = {"step": "search", "text": "Searched VNIT's pages and documents"
                   + (f" in {len(sub_questions)} parts" if len(sub_questions) > 1 else "") + "."}

    # Ask which group the student means when the answer depends on it. Once
    # per question: asked again straight after (the student ignored the
    # choices and typed it again), it is answered as it stands.
    repeated = bool(history) and history[-1].strip() == asked
    if clarify_enabled() and not repeated:
        passages = [r for r, _ in generate.select_passages(report)][:CLARIFY_PASSAGES]
        clarify = slots.needs_clarification(searched, topic, passages, profile)
        if clarify:
            groups = ", ".join(c["label"] for c in clarify["choices"])
            trace.append(search_note)
            trace.append({"step": "clarify",
                          "text": f"Your question fits several different documents ({groups}) "
                                  "with different answers, so I asked which one you mean."})
            return {
                "question": asked,
                "understood_as": searched if rewrite_note else None,
                "answer": clarify["question"],
                "clarify": clarify,
                "sources": [],
                "mode": "clarify",
                "kind": kind,
                "intent": topic,
                "sub_questions": sub_questions,
                "trace": trace,
                "verification": None,
            }

    if use_agent:
        grade, extra, grade_note = None, [], None
        if gate_enabled():
            grade = grader.grade(searched, report)
            extra = corrective_passages(searched, report) if grade["grade"] != "correct" else []
            grade_note = {"step": "grade", "verdict": grade["grade"], "text": _grade_text(grade, extra)}
        try:
            result = planner.run(searched, report, extra=extra, search_grade=grade)
            steps = result["trace"]
            if grade_note:
                steps = steps[:1] + [grade_note] + steps[1:]  # right after the first search
            return hand_off({
                "question": asked,
                "understood_as": searched if rewrite_note else None,
                "answer": result["answer"],
                "sources": result["sources"],
                "mode": result["mode"],
                "kind": kind,
                "intent": topic,
                "sub_questions": sub_questions,
                "trace": trace + steps,
                "verification": result["verification"],
                "usage": result["usage"],
            })
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
    return hand_off({
        "question": asked,
        "understood_as": searched if rewrite_note else None,
        "answer": composed["answer"],
        "sources": composed["sources"],
        "mode": composed["mode"],
        "kind": kind,
        "intent": topic,
        "sub_questions": sub_questions,
        "trace": trace,
        "verification": check,
    })


FALLBACK_TOKENS = 3000

CONTACTS_PATH = Path(__file__).parent.parent / "data" / "contacts.json"
_contacts = {}


def contacts() -> dict:
    """Topic -> the office to contact (data/contacts.json, copied by hand from VNIT's pages)."""
    if not _contacts:
        data = json.loads(CONTACTS_PATH.read_text(encoding="utf-8"))
        _contacts.update({k: v for k, v in data.items() if not k.startswith("_")})
    return _contacts


def hand_off(reply: dict) -> dict:
    """When the answer says the documents don't cover it, add who can help.

    A refusal used to be a dead end. Commercial university assistants route
    the questions they cannot answer to the right office; here the office comes
    from a hand-checked file, not from the LLM, so it is not verified again.
    Only answers written by an LLM qualify: a quoted-passages answer is not a
    refusal, and a topic with no known office gets nothing rather than a guess.
    """
    contact = contacts().get(reply.get("intent"))
    check = reply.get("verification") or {}
    written = str(reply["mode"]).startswith(("agent", "llm"))
    if not (contact and written and (verifier.is_refusal(reply["answer"])
                                     or check.get("verdict") == "unsupported")):
        return reply
    reply["answer"] += (f"\n\n**Who can help:** {contact['office']} — "
                        f"{contact['email']}, {contact['phone']}")
    if contact["source_url"] not in {s["url"] for s in reply["sources"]}:
        reply["sources"] = reply["sources"] + [{"title": contact["office"],
                                                "url": contact["source_url"], "date": ""}]
    reply["trace"] = reply["trace"] + [{"step": "handoff", "text": (
        "I couldn't find this in VNIT's documents, so I've added who to contact."
        if verifier.is_refusal(reply["answer"]) else
        "Part of this answer could not be confirmed, so I've added who to contact.")}]
    return reply

# Pages whose titles best match the question, looked inside when the first
# search grades weak (grader.py), and passages kept from each.
CORRECTIVE_DOCUMENTS = 2
CORRECTIVE_PASSAGES = 2


CLARIFY_PASSAGES = 7


def clarify_enabled() -> bool:
    return os.environ.get("CLARIFY", "on").strip().lower() not in ("off", "0", "false", "no")


def gate_enabled() -> bool:
    return os.environ.get("CRAG_GATE", "on").strip().lower() not in ("off", "0", "false", "no")


def corrective_passages(question: str, report: dict) -> list:
    """Look inside the best-titled pages the first search did not reach.

    The planner could do this itself with find_documents and read_document, and
    for the 2025-26 placement figures it never did (EXPERIMENTS-LOG §20c). Done
    here as code, it costs no LLM call and happens every time the first search
    looks weak. Returns (result, text) pairs, at most one per page, and only
    passages the reranker scores above grader.LOW.
    """
    import query

    reached = {r["source_url"] for r, _ in generate.select_passages(report)}
    catalogue = query.list_sources()
    found = []
    candidates = [catalogue[i]["url"] for _score, i in tools._title_scores(question)
                  if catalogue[i]["url"] not in reached][:CORRECTIVE_DOCUMENTS]
    for url in candidates:
        best = query.retrieve_within(question, [url], k=CORRECTIVE_PASSAGES)[:1]
        if best and best[0]["rerank"] is not None and best[0]["rerank"] > grader.LOW:
            r = best[0]
            text = r["text"]
            if len(text) > generate.MAX_CHUNK_CHARS:
                text = text[:generate.MAX_CHUNK_CHARS].rsplit(" ", 1)[0] + "..."
            found.append((r, text))
    return found


def _grade_text(grade: dict, extra) -> str:
    if grade["grade"] == "correct":
        if grade["top"] is None:
            return "Could not grade the first search (no reranker), so used it as it was."
        return f"The first search looked relevant (score {grade['top']:.1f})."
    if not extra:
        return (f"The first search looked weak ({grade['why']}); no better-titled page had a "
                "relevant passage, so I continued with what it found.")
    titles = " and ".join(f"“{r['title']}”" for r, _ in extra)
    return f"The first search looked weak ({grade['why']}), so I also looked inside {titles}."

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
