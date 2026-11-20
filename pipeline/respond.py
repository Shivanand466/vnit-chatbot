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
import re
from pathlib import Path

import agent
import agent_loop
import followup
import generate
import grader
import language
import memory
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


def v2_enabled() -> bool:
    """Agent v2 (Runbook 11): on unless AGENT_V2=off, which gives v1's exact behaviour."""
    return planner.switched_on("AGENT_V2")


# v1 resolved a follow-up against this many earlier questions (api/main.py).
V1_HISTORY = 3


def answer(question: str, history=None, k: int = 7, use_agent: bool = None,
           profile: dict = None, turns=None, emit=None, cancel=None) -> dict:
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

    `turns` (v2) are the earlier questions with the answers given, as the chat
    page sends them; memory.py trims them. They help read a follow-up and are
    shown to the agent as context, never as evidence. With AGENT_V2=off only
    their questions are used, as v1's `history`.

    v2 also detects the language (language.py) and the task type
    (router.task), answers a general concept question briefly and labelled,
    and adds `suggestions`. `emit(event, data)` receives the steps and the
    answer as they happen (api /ask/stream); `cancel` stops the work.
    """
    use_agent = agent_enabled() if use_agent is None else use_agent
    asked = (question or "").strip()
    v2 = v2_enabled()
    remembered = memory.clean_turns(turns)
    if remembered and not history:
        history = memory.questions(remembered)
        history = history if v2 else history[-V1_HISTORY:]
    if not v2:
        remembered = []
    trace = agent_loop._Trace(emit)

    lang, to_search, lang_note = language.ENGLISH, asked, False
    if v2:
        lang = language.detect(asked)
        chat = language.chat_kind(asked) if lang != language.ENGLISH else None
        if chat:
            trace.append({"step": "route", "text": ROUTE_NOTES[chat]})
            return _finish({"question": asked, "understood_as": None,
                            "answer": language.REPLIES.get((lang, chat), DIRECT_ANSWERS[chat]),
                            "sources": [], "mode": f"direct ({chat})", "kind": chat, "intent": None,
                            "sub_questions": [], "trace": list(trace), "verification": None},
                           router.TASK_CHAT, lang)
        if lang != language.ENGLISH:
            to_search = language.english_keywords(asked, lang)
            lang_note = to_search != asked
            trace.append({"step": "understand", "text": f"The question is in {language.NAMES[lang]}, "
                          f"so I searched in English: “{to_search}”; the answer will be in "
                          f"{language.NAMES[lang].split(' (')[0]}."})

    searched, rewrite_note = followup.resolve(to_search, history or [], turns=remembered or None)
    kind = router.route(searched)
    task = router.task(searched) if v2 else None

    if rewrite_note:
        trace.append({"step": "understand",
                      "text": f"Read the follow-up with the earlier questions as: “{searched}”"})
    rewrite_note = rewrite_note or lang_note
    trace.append({"step": "route", "text": ROUTE_NOTES[kind]})
    if task and task not in (router.TASK_LOOKUP, router.TASK_CHAT):
        trace.append({"step": "route", "text": f"Task: {task}."})
    if task == router.TASK_GENERAL and use_agent and os.environ.get("GENAI_API_KEY"):
        try:
            return _finish(general_answer(asked, searched, lang, trace), task, lang)
        except agent_loop.Cancelled:
            raise
        except Exception as e:
            trace.append({"step": "fallback", "text": f"Could not write a general answer "
                          f"({_short(e)}), so I searched VNIT's documents instead."})
    topic = None if kind in router.NO_SEARCH else router.intent(searched)
    if topic:
        trace.append({"step": "route", "text": f"Topic: {topic}."})
        # CLARIFY=off switches off the whole of clarify-or-assume, the profile too.
        searched, profile_note = slots.apply_profile(
            searched, topic, profile if clarify_enabled() else None)
        if profile_note:
            rewrite_note = True
            trace.append({"step": "understand", "text": profile_note})

    if kind in router.NO_SEARCH:
        direct = DIRECT_ANSWERS[kind]
        if v2 and kind == router.CAPABILITY:
            direct = CAPABILITY_ANSWER_V2
        return _finish({
            "question": asked,
            "understood_as": searched if rewrite_note else None,
            "answer": direct,
            "sources": [],
            "mode": f"direct ({kind})",
            "kind": kind,
            "intent": topic,
            "sub_questions": [],
            "trace": trace,
            "verification": None,
        }, task, lang)

    _check_cancel(cancel)
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
            return _finish({
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
            }, task, lang)

    if use_agent:
        grade, extra, grade_note = None, [], None
        if gate_enabled():
            grade = grader.grade(searched, report)
            extra = corrective_passages(searched, report) if grade["grade"] != "correct" else []
            grade_note = {"step": "grade", "verdict": grade["grade"], "text": _grade_text(grade, extra)}
            rows = table_rows(searched, topic, report)
            if rows:
                extra = extra + rows
                grade_note["text"] += " I also looked up matching rows in the documents' tables."
        try:
            if v2:
                if grade_note and emit:
                    emit("step", grade_note)
                result = agent_loop.run(
                    searched, report, extra=extra, search_grade=grade, turns=remembered,
                    instructions=[router.TASK_LINES.get(task, ""), language.instruction(lang)],
                    emit=emit, cancel=cancel)
            else:
                result = planner.run(searched, report, extra=extra, search_grade=grade,
                                     conversation=memory.prompt_block(remembered))
            steps = result["trace"]
            if grade_note:
                steps = steps[:1] + [grade_note] + steps[1:]  # right after the first search
            return _finish(hand_off({
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
            }), task, lang)
        except agent_loop.Cancelled:
            raise
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
    return _finish(hand_off({
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
    }), task, lang)


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise agent_loop.Cancelled()


def _finish(reply: dict, task, lang) -> dict:
    """The last touches: v2 adds the task, language and suggested follow-ups; v1 is left as it was."""
    reply["trace"] = list(reply["trace"])
    if task is None:
        return reply
    if task == router.TASK_DRAFT and str(reply["mode"]).startswith(("agent", "llm")):
        reply["answer"] = label_draft(reply["answer"])
    reply["task"] = task
    reply["language"] = lang
    reply["suggestions"] = suggestions(reply)
    return reply


DRAFT_LABEL = "Draft — check before sending."


def label_draft(text: str) -> str:
    """A draft always says it is one, whether or not the model wrote the label."""
    if re.search(r"draft\s*[—–-]+\s*check before sending", text[:200], re.I):
        return text
    return f"{DRAFT_LABEL}\n\n{text}"


GENERAL_LABEL = "*General answer, not from VNIT's documents.*"
GENERAL_PROMPT = (
    "A VNIT Nagpur student asked what a general term means. Explain it briefly (under 80 "
    "words) from general knowledge, the way a senior student would. This answer is not about "
    "VNIT: give no VNIT-specific figures, dates, fees, ranks, cut-offs, names or contacts, and no "
    "numbers at all unless they are part of the definition. Do not claim anything about VNIT's "
    "own rules; if those matter, end by saying they can ask how VNIT applies it."
)


def general_answer(asked: str, searched: str, lang: str, trace) -> dict:
    """A short, labelled answer to a general concept question ("what is CGPA?").

    One LLM call, no search. The verifier is run with no passages at all, so
    any figure in the answer is flagged: a general answer must carry no VNIT
    figure, and a figure it does carry is shown as unconfirmed.
    """
    api_key = os.environ.get("GENAI_API_KEY")
    base_url = os.environ.get("GENAI_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.environ.get("AGENT_MODEL", "openai/gpt-oss-120b")
    llm = planner._LLM(api_key, base_url, model)
    system = GENERAL_PROMPT + ("\n\n" + language.instruction(lang) if lang != language.ENGLISH else "")
    message = llm.chat([{"role": "system", "content": system},
                        {"role": "user", "content": asked}],
                       tools_on=False, extra=agent_loop.model_extras(model))
    text = agent_loop.strip_think(message.get("content") or "")
    if not text:
        raise planner.AgentUnavailable("the model returned no answer")
    check = verifier.verify(text, [], searched)
    trace.append({"step": "answer", "text": "Answered from general knowledge, without searching, "
                                            "and labelled it as not from VNIT's documents."})
    trace.append({"step": "verify", "text": ("No VNIT figures in this general answer." if
                                             check["verdict"] != "unsupported" else
                                             verifier.summary(check)), "verdict": check["verdict"]})
    if check["verdict"] == "unsupported":
        text += (f"\n\nNote: {', '.join(check['unsupported'])} is general information, not "
                 "checked against VNIT's documents; ask me about VNIT's own rules to get a sourced answer.")
    return {"question": asked, "understood_as": None, "answer": f"{GENERAL_LABEL}\n\n{text}",
            "sources": [], "mode": f"general ({model})", "kind": router.LOOKUP, "intent": None,
            "sub_questions": [], "trace": list(trace), "verification": check,
            "usage": {"llm_calls": llm.calls, "tokens": llm.tokens, "tool_calls": 0}}


# Suggested follow-ups, by topic: each is a question from check_answers.py's
# cases that the chatbot is known to answer (the saved results pass), so a
# suggestion never leads a student into a dead end. {programme} is filled from
# the question or profile when it names one with its own fee sheets.
SUGGESTIONS = {
    router.FEES: ["What is the hostel fee for first year {programme} boys for the Winter 2026 session?",
                  "What is the extended last date to apply for fee remission 2026-27?",
                  "Can I apply for fee remission if I already have another scholarship?",
                  "What is the yearly tuition fee for {programme} students in the OPEN category?"],
    router.HOSTEL: ["What is the hostel fee for first year {programme} girls for the Winter 2026 session?",
                    "How much is the hostel mess charge per day now?",
                    "What is the extended last date to apply for fee remission 2026-27?",
                    "When can first year students join the hostel mess?",
                    "Can I keep a refrigerator in my hostel room at VNIT?"],
    router.CALENDAR: ["When are the end semester exams for first year B.Tech in Winter 2026?",
                      "When is the mid semester exam for slot A in Winter 2026?",
                      "Is Holi a holiday at VNIT in 2026? Which date?",
                      "When is the convocation in 2026?"],
    router.SCHOLARSHIP: ["What is the application deadline for the Shiksha Shakti Scholarship 2026-27?",
                         "How much money does the Kotak Kanya Scholarship give per year?",
                         "What is the last date to apply for the IDFC FIRST Bank Engineering Scholarship?"],
    router.PLACEMENT: ["How many students got placed in 2025-26 and how many companies came?",
                       "What was the average package for B.Tech in 2024-25?",
                       "Until what date can batch 2027 students upgrade a placement offer?"],
    router.ADMISSION: ["How many undergraduate students does Civil Engineering enroll annually?",
                       "When is the orientation program for new B.Tech students in 2026?",
                       "Is the seat acceptance fee refundable for Study in India students?"],
    router.PEOPLE: ["Who is the current Director of VNIT?", "Who is the Registrar of VNIT Nagpur?",
                    "What is the email of the Dean (Academic)?"],
    router.DEPARTMENT: ["What specializations does the Electrical Engineering M.Tech offer?",
                        "When was the Computer Science and Engineering department established?",
                        "Tell me about the 5G lab and when was it announced"],
    router.RULES: ["What CGPA do I need to take a minor degree?",
                   "What happens if my attendance is below 75% in an M.Tech course?",
                   "What is the yearly tuition fee for B.Tech students in the OPEN category?"],
    router.OTHER: ["What are the library timings on weekdays?", "Who is the current Director of VNIT?",
                   "What is the hostel fee for first year {programme} boys for the Winter 2026 session?"],
}
_FEE_PROGRAMMES = {"btech": "B.Tech", "mtech": "M.Tech"}
MAX_SUGGESTIONS = 3


def suggestions(reply: dict) -> list:
    """2-3 follow-up questions for the chips under an answer, in code (no LLM call).

    From the topic's known-answerable questions, skipping any that repeat what
    was just asked; a draft or a procedure also gets "whom to contact".
    """
    if str(reply.get("mode", "")).startswith(("direct", "clarify")) and reply.get("kind") != router.CAPABILITY:
        return []
    asked = reply.get("understood_as") or reply.get("question") or ""
    programme = next((_FEE_PROGRAMMES[p] for p in slots.extract(asked).values() if p in _FEE_PROGRAMMES),
                     "B.Tech")
    asked_words = tools._words(asked)
    chosen = []
    for template in SUGGESTIONS.get(reply.get("intent") or router.OTHER, SUGGESTIONS[router.OTHER]):
        text = template.format(programme=programme)
        words = tools._words(text)
        if words and len(words & asked_words) / len(words) >= 0.6:
            continue  # the same question again
        chosen.append(text)
    if reply.get("task") in (router.TASK_DRAFT, router.TASK_EXPLAIN):
        chosen.insert(0, "Which office should I contact about this, and how?")
    return chosen[:MAX_SUGGESTIONS]


CAPABILITY_ANSWER_V2 = (
    "I answer questions about **VNIT Nagpur** using only the institute's own website and the "
    "documents it publishes. I show the source of every answer and check every figure against it.\n\n"
    "I can:\n"
    "- look up facts: fees, hostels, scholarships, calendars and exams, placements, departments, contacts\n"
    "- compare things in a table (*\"B.Tech vs B.Arch fees\"*)\n"
    "- summarise a notice or document (*\"summarise the hostel rules\"*)\n"
    "- explain a procedure step by step (*\"how do I apply for fee remission?\"*)\n"
    "- draft an email or application to the right office, with its address\n"
    "- check the newest notices, today's date, or a live vnit.ac.in page\n"
    "- answer in Hindi, Marathi or Hinglish\n"
    "- remember our conversation, so *\"how do I pay it?\"* works\n\n"
    "If something isn't in VNIT's material, I say so rather than guessing."
)


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
# Table rows added to every fees, calendar or placement question (table_rows).
TABLE_TOPICS = (router.FEES, router.CALENDAR, router.PLACEMENT)
TABLE_ROWS_ADDED = 2
TABLE_MIN_WORDS = 2
TABLE_CANDIDATES = 40   # rows fetched before the best TABLE_ROWS_ADDED are chosen
TABLE_ROW_CHARS = 450    # about 150 tokens a row in the first prompt


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


def table_rows(question: str, topic: str, report: dict) -> list:
    """The best table rows for a fees, calendar or placement question, as
    corrective passages.

    The answer to these is often one row of a long table (a holiday list, a
    fee sheet, a placement report), and the other rows of the same table can
    fill its places in the passage search before the right one is reranked
    (EXPERIMENTS-LOG §35). facts.db holds every row on its own, and the agent's
    lookup_table tool can find it, but the agent rarely calls it. This looks
    the rows up in code, as the tool would: the question's rarer words as
    keywords, its programme, gender, category, year and academic year as
    filters. A row is kept only when it holds at least TABLE_MIN_WORDS of
    those words; the rows naming the question's rarest words in their own
    label and cells come first. No LLM call.
    """
    import tools

    if topic not in TABLE_TOPICS:
        return []
    words = grader.key_words(question)
    if len(words) < TABLE_MIN_WORDS:
        return []
    tags = {k: v for k, v in slots.extract(question).items() if k in tools.TABLE_TAGS}
    year = re.search(r"\b(20\d{2})\s*[-–/]\s*(\d{2})\b", question)
    if year:
        tags["academic_year"] = f"{year.group(1)}-{year.group(2)}"
    idf = grader._idf()
    scored = []
    for n, r in enumerate(tools.lookup_table(" ".join(words), limit=TABLE_CANDIDATES, **tags)):
        held = tools._words(_undotted(f"{r['title']} {r['text']}"))
        if sum(1 for w in words if w in held) < TABLE_MIN_WORDS:
            continue
        # Judge the row by its own label and cells, not the lead-in and title
        # every row of its table shares, and by how rare the words it holds
        # are: "Holi" names one row, "holiday" names every row of the list.
        own = tools._words(_undotted(" | ".join(r["text"].rsplit(" | ", 2)[-2:])))
        scored.append((-sum(idf.get(w, 0.0) for w in words if w in own), n, r))
    found, documents = [], set()
    for _s, _n, r in sorted(scored, key=lambda t: t[:2]):
        if r["source_url"] in documents:
            continue  # one row per document, as the search caps passages per source
        documents.add(r["source_url"])
        text = r["text"]
        if len(text) > TABLE_ROW_CHARS:  # a calendar row can hold dozens of cells
            text = text[:TABLE_ROW_CHARS].rsplit(" ", 1)[0] + "..."
        found.append((r, text))
        if len(found) == TABLE_ROWS_ADDED:
            break
    return found


def _undotted(text: str) -> str:
    """"B.Tech" as "BTech", "Ph.D" as "PhD": a question says "btech", a table "B.Tech"."""
    return _DOTTED.sub(r"\1\2", text)


_DOTTED = re.compile(r"\b([A-Za-z]{1,2})\.\s?([A-Za-z]{1,4})\b")


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
