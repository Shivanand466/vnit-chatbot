"""
Agent v2: plan, act, observe, repeat -- until the question is answered or the budget is spent.

v1's planner (planner.py) allowed two rounds of at most two tool calls, then
had to answer. That kept a question within Groq's free tier, but a question
with three parts, or one whose first two searches missed, ran out of turns
before it ran out of ideas. Claude and ChatGPT keep going until they have what
they need. This loop does the same, within limits a free tier can pay for:

    plan      the first reply may list 1-4 parts ("1. Find the S-27 fee notice.
              2. Look up the hostel fee row."), shown in the trace; the loop
              tracks which parts are done;
    act       up to MAX_STEPS rounds, up to MAX_PARALLEL tool calls per round,
              run at the same time (the tools only read);
    observe   after each round, code -- not another LLM call -- says in one line
              what the round found ("nothing new about the due date; try the
              fee notice itself"), and how many steps and tokens are left;
    stop      when the model answers, every plan part is done, the next round
              would pass the token budget, or two rounds in a row found nothing
              new;
    answer    from a clean prompt over all the evidence (planner._final_prompt),
              verified figure by figure (verifier.py), revised once if needed.

The pieces that already work -- the client and its rate pacer, Evidence, the
final prompt, citations, the verifier -- are imported from planner.py and
tools.py, not copied, so v1 and v2 differ only in the loop.

When the prompt grows past planner.PROMPT_BUDGET, older passages are set aside
(the ones the model cited and the newest stay) and the model is told their
titles, so it can reopen one with read_document.

The answer can be streamed (`emit`): steps as they happen, then the answer as
the model writes it, with [P3] labels turned into [1] on the fly. `cancel` (a
threading.Event) stops the loop at the next step or token.
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import generate
import grader
import memory
import planner
import tools
import verifier

MAX_PARALLEL = 3
MAX_PLAN_PARTS = 4
STUCK_ROUNDS = 2
# Passage text kept when the conversation is compacted (about 3,000 tokens).
COMPACT_CHARS = 9000
# Tokens a tool-calling reply usually takes, for judging whether one more round fits the budget.
REPLY_ESTIMATE = 300


def max_steps() -> int:
    return max(1, int(os.environ.get("AGENT_V2_MAX_STEPS", "6")))


def budget() -> int:
    """Tokens one question may spend (AGENT_V2_BUDGET): a free tier day is ~200,000."""
    return max(2000, int(os.environ.get("AGENT_V2_BUDGET", "14000")))


class Cancelled(Exception):
    """The student pressed Stop (the page disconnected)."""


# ---------------------------------------------------------------------------
# The plan, and how code judges a round
# ---------------------------------------------------------------------------

_PLAN_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.{4,200})$")
_DONE = re.compile(r"\bdone\s*:\s*((?:\d+\s*(?:,|and|&)?\s*)+)", re.I)
_THINK = re.compile(r"<think>.*?(</think>|$)", re.S)


def strip_think(text: str) -> str:
    """Some open models write their reasoning inline as <think>...</think>; never show it."""
    return _THINK.sub("", text or "").strip()


def parse_plan(text: str) -> list:
    """The numbered or bulleted lines of a reply, as plan parts (at most MAX_PLAN_PARTS)."""
    parts = []
    for line in strip_think(text).splitlines():
        m = _PLAN_LINE.match(line)
        if m and not _DONE.search(line):
            parts.append(m.group(1).strip())
    return parts[:MAX_PLAN_PARTS]


def parse_done(text: str) -> set:
    """Plan parts the model says it now has: "Done: 1, 3"."""
    found = set()
    for m in _DONE.finditer(text or ""):
        found |= {int(n) for n in re.findall(r"\d+", m.group(1))}
    return found


_KINDS = [
    ("date", re.compile(r"\b(when|date|deadline|last day|due|till|until|schedule|holiday)\b", re.I)),
    ("money", re.compile(r"\b(fee|fees|cost|price|charges?|amount|how much|rs\.?|rupees|tuition|"
                         r"stipend|package|salary|ctc)\b|₹", re.I)),
    ("contact", re.compile(r"\b(email|e-mail|phone|contact|call|reach|write to)\b", re.I)),
    ("count", re.compile(r"\bhow many\b|\bnumber of\b|\bseats?\b|\bintake\b", re.I)),
]
_HAS = {
    "date": re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+"
                       r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*|\b(?:jan|feb|mar|apr|may|"
                       r"jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}\b", re.I),
    "money": re.compile(r"\b\d{1,3}(?:,\d{2,3})+\b|\b\d{4,7}(?:\.\d+)?\b|rs\.?\s*\d|₹\s*\d|\blakh\b", re.I),
    "contact": re.compile(r"@[\w-]+\.|\b\d{3,5}[ -]\d{6,8}\b", re.I),
    "count": re.compile(r"\b\d{1,5}\b"),
}
_KIND_WORDS = {"date": "a date", "money": "an amount", "contact": "an email or phone number",
               "count": "a number"}


def asked_kind(question: str):
    """What kind of fact the question wants: date, money, contact, count, or None."""
    for kind, pattern in _KINDS:
        if pattern.search(question or ""):
            return kind
    return None


def _holds_kind(text: str, kind) -> bool:
    return kind is None or bool(_HAS[kind].search(text or ""))


# The verbs a plan is written in ("Find the fee", "Look up the row") are
# instructions, not what the passage should say; "find" is rare in VNIT's
# documents, so left in it would be a key word no passage covers.
_PLAN_VERBS = re.compile(r"\b(find|finding|look(ing)?\s+up|look\s+for|search(ing)?(\s+for)?|check|get|"
                         r"locate|confirm|identify|determine|open|read|see|fetch|calculate|compute|"
                         r"compare|verify|retrieve|list|state|give)\b", re.I)


def part_covered(part: str, passages) -> bool:
    """Whether some passage both talks about this plan part and holds the kind of fact it needs.

    Most of the part's key words in one passage (grader.COVER, the corrective
    gate's rule), plus a figure or date when the part asks for one.
    """
    words = grader.key_words(_PLAN_VERBS.sub(" ", part))
    if not words:
        return False
    kind = asked_kind(part)
    for p in passages:
        held = tools._words(f"{p['result'].get('title', '')} {p['text']}")
        if sum(1 for w in words if w in held) >= grader.COVER * len(words) and _holds_kind(p["text"], kind):
            return True
    return False


def reflect(question: str, new_passages, open_parts) -> str:
    """One line, written by code, on what the last round found and what to try next."""
    kind = asked_kind(open_parts[0] if open_parts else question)
    wanted = _KIND_WORDS.get(kind, "the answer")
    if not new_passages:
        return ("That round found nothing new. Try different words (the ones a notice or fee "
                "sheet would use), or find the document itself with find_documents and open it "
                "with read_document.")
    titles = "; ".join(dict.fromkeys(p["result"].get("title", "") for p in new_passages))[:160]
    if kind and not any(_holds_kind(p["text"], kind) for p in new_passages):
        return (f"That round found {len(new_passages)} new passage(s) ({titles}) but none gives "
                f"{wanted}. Try the document that should state it, e.g. the notice or fee sheet "
                "itself, or lookup_table for a row of its table.")
    return f"That round found {len(new_passages)} new passage(s) with {wanted} ({titles})."


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

TOOL_GUIDE = {
    "search_vnit": "search_vnit: search everything again with other words.",
    "find_documents": "find_documents: find a document by its title.",
    "read_document": "read_document: search inside one document (call it again to read more).",
    "lookup_table": "lookup_table: a fee, date or count from a document's table; often the fastest.",
    "calculate": "calculate: any total or difference, exactly.",
    "latest_notices": "latest_notices: the newest notices, for 'any new notice?' questions.",
    "fetch_vnit_page": "fetch_vnit_page: open a live vnit.ac.in page, to check what it says now.",
    "today": "today: today's date, for 'is it over?' or 'what's next?' questions.",
    "contact_office": "contact_office: the office, email and phone to contact for a topic.",
}


def system_prompt(schemas, steps: int, tokens: int, instructions=()) -> str:
    offered = [s["function"]["name"] for s in schemas]
    guide = "\n".join(f"- {TOOL_GUIDE[n]}" for n in offered if n in TOOL_GUIDE)
    extra = ("\n\n" + "\n".join(i for i in instructions if i)) if any(instructions) else ""
    return (
        "You are the VNIT Nagpur student helpdesk agent. You answer students' questions "
        "about VNIT using only passages from VNIT's own website and documents, which you "
        f"get with your tools. Today's date is {date.today():%d %B %Y}.\n\n"
        "The results of a first search are already in the conversation. Each passage is "
        "labelled like [P3 · doc S57]: P3 is the passage, S57 the page or document it "
        "comes from.\n\n"
        "Work like this:\n"
        "- If the passages already answer every part of the question, answer straight away, "
        "with no plan and no tool calls.\n"
        "- Otherwise, first write a short plan: 1 to 4 numbered lines, one per part of the "
        "question (\"1. Find the B.Tech tuition fee. 2. Find the due date.\"), then call the "
        f"tools you need. You may call up to {MAX_PARALLEL} tools at once.\n"
        "- After each round, write \"Done: \" and the numbers of the plan parts you now have, "
        "and act on what is still open. Keep going until every part is done, then answer.\n"
        f"- You have up to {steps} rounds of tools and about {tokens:,} tokens for this "
        "question; each round's message says how many are left. If the material still does "
        "not answer a part, say so plainly -- never guess.\n\n"
        f"Tools:\n{guide}\n\n"
        "Cite the passages you used by their label right after each fact, like [P3]. "
        "Cite only passages you were shown. Earlier answers in the conversation are context, "
        f"not sources.{extra}\n\n"
        f"{generate.ANSWER_GUIDE}"
    )


def final_messages(question, evidence, calculations, conversation="", instructions=()):
    """planner._final_prompt, plus the conversation and this task's instructions."""
    messages, pids = planner._final_prompt(question, evidence, calculations)
    lines = [i for i in instructions if i]
    if lines:
        messages[0]["content"] += "\n\n" + "\n".join(lines)
    if conversation:
        messages[1]["content"] = conversation + messages[1]["content"]
    return messages, pids


def _passage_block(p) -> str:
    return (f"[{p['pid']} · doc {tools.doc_id(p['result']['source_url'])}] "
            f"{generate.passage_header(p['result'])[1:-1]}\n{p['text']}")


def compact(question, evidence, cited, header=""):
    """A fresh first message holding the passages worth keeping, and the titles set aside.

    Kept first: what the model cited, then what the tools found (newest first),
    then the first search. Returns (message text, titles set aside).
    """
    order = ([p for p in evidence.passages if p["pid"] in cited]
             + [p for p in reversed(evidence.passages) if p["origin"] != "first" and p["pid"] not in cited]
             + [p for p in evidence.passages if p["origin"] == "first" and p["pid"] not in cited])
    kept, aside, used = [], [], 0
    for p in order:
        block = _passage_block(p)
        if used + len(block) > COMPACT_CHARS and kept:
            aside.append(p)
            continue
        kept.append(p)
        used += len(block)
    kept.sort(key=lambda p: int(p["pid"][1:]))
    titles = list(dict.fromkeys(f"doc {tools.doc_id(p['result']['source_url'])} "
                                f"{p['result'].get('title', '')}" for p in aside))
    note = ("\n\nSet aside to save space (reopen with read_document if needed): "
            + "; ".join(titles)) if titles else ""
    text = (f"{header}Student's question: {question}\n\nPassages found so far:\n\n"
            + "\n\n".join(_passage_block(p) for p in kept) + note)
    return text, titles


# ---------------------------------------------------------------------------
# Model calls: per-model extras, streaming
# ---------------------------------------------------------------------------

def model_extras(model: str) -> dict:
    """Payload fields some models need. Qwen3 thinks aloud unless told not to (Groq's
    reasoning_format); gpt-oss gets nothing extra, so its requests stay as v1's."""
    if "qwen" in (model or "").lower():
        return {"reasoning_format": "hidden"}
    return {}


class LiveText:
    """Turns the growing raw answer into what the student sees, and emits the new part.

    Labels are numbered as the final answer will number them ([P3] -> [1]); a
    label still being written ("[P") is held back until it closes.
    """

    def __init__(self, evidence, emit):
        self.evidence, self.emit, self.sent = evidence, emit, ""

    def update(self, raw: str):
        text = strip_think(raw)
        cut = max(text.rfind("["), text.rfind("【"))
        if cut >= 0 and not re.search(r"[\]】]", text[cut:]) and len(text) - cut < 40:
            text = text[:cut]
        shown = planner._citations_to_sources(text, self.evidence)[0]
        if shown.startswith(self.sent) and len(shown) > len(self.sent):
            self.emit("token", shown[len(self.sent):])
            self.sent = shown


def stream_text(llm, messages, on_text, cancel=None) -> str:
    """The model's answer to a tool-free prompt, read as it is written (Groq's "stream": true).

    Falls back to an ordinary call when the stream fails or comes back empty, so
    streaming can only change how the answer arrives, never whether it does.
    """
    import requests

    payload = {"model": llm.model, "messages": messages, "max_tokens": planner.MAX_TOKENS,
               "temperature": 0, "stream": True}
    payload.update(model_extras(llm.model))
    llm.waited += planner._pacer_for(llm.model).wait_for(planner._estimate_tokens(payload))
    try:
        resp = requests.post(f"{llm.base_url}/chat/completions",
                             headers={"Authorization": f"Bearer {llm.api_key}"},
                             json=payload, timeout=45, stream=True)
    except Exception:
        return _plain(llm, messages)
    llm.calls += 1
    planner._pacer_for(llm.model).update(resp.headers)
    if resp.status_code != 200:
        resp.close()
        return _plain(llm, messages)
    text = ""
    try:
        for line in resp.iter_lines(decode_unicode=True):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            usage = (chunk.get("x_groq") or {}).get("usage") or chunk.get("usage")
            if usage:
                llm.tokens += usage.get("total_tokens", 0)
            for choice in chunk.get("choices") or []:
                piece = (choice.get("delta") or {}).get("content") or ""
                if piece:
                    text += piece
                    on_text(text)
    finally:
        resp.close()
    return strip_think(text) or _plain(llm, messages)


def _plain(llm, messages) -> str:
    try:
        message = llm.chat(messages, tools_on=False, extra=model_extras(llm.model))
    except planner._ToolUseFailed:
        raise planner.AgentUnavailable("the model kept calling tools instead of answering")
    return strip_think(message.get("content") or "")


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

class _Trace(list):
    """The trace, which also tells a stream about each step as it is added."""

    def __init__(self, emit=None):
        super().__init__()
        self.emit = emit

    def append(self, item):
        super().append(item)
        if self.emit:
            self.emit("step", item)


def _run_calls(calls, evidence, made):
    """Run one round's tool calls at the same time; results in the order asked.

    A call identical to one already made (`made`, the set of earlier calls) is
    not run again: seen live, the dev model asked read_document the same thing
    twice in a row, and the repeat could only return what it already had.
    """
    def run(c):
        key = (c["name"], json.dumps(c["args"], sort_keys=True))
        if key in made:
            return {"observation": "You already made exactly this call above; its result has not "
                                   "changed. Try other words, another document, or another tool.",
                    "summary": f"Skipped a repeat of an earlier {c['name']} call"}
        made.add(key)
        return tools.run_tool(c["name"], c["args"], evidence)

    if len(calls) == 1:
        return [run(calls[0])]
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        return list(pool.map(run, calls))


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def run(question: str, report: dict, api_key: str = None, base_url: str = None,
        model: str = None, extra=None, search_grade: dict = None, turns=None,
        instructions=(), schemas=None, emit=None, cancel=None) -> dict:
    """Answer `question` starting from the first search `report`, as planner.run does.

    `turns` are the trimmed earlier turns (memory.py), shown as context only.
    `instructions` are extra lines for this task or language (router.task,
    language.py). `schemas` are the tools offered (default: every v2 tool).
    `emit(event, data)` receives "step", "token" and "replace" events while it
    runs; `cancel` stops it. Returns the same fields as planner.run.
    """
    api_key = api_key or os.environ.get("GENAI_API_KEY")
    base_url = base_url or os.environ.get("GENAI_BASE_URL", "https://api.groq.com/openai/v1")
    model = model or os.environ.get("AGENT_MODEL", "openai/gpt-oss-120b")
    if not api_key:
        raise planner.AgentUnavailable("no GENAI_API_KEY set")
    say = emit or (lambda event, data: None)
    schemas = tools.active_schemas(v2=True) if schemas is None else schemas
    steps_allowed, tokens_allowed = max_steps(), budget()
    extras = model_extras(model)

    llm = planner._LLM(api_key, base_url, model)
    evidence = tools.Evidence()
    trace = _Trace(emit)
    conversation = memory.prompt_block(turns or [])

    first = generate.select_passages(report)
    first_block = []
    for r, text in first:
        pid, _ = evidence.add(r, text, origin="first")
        first_block.append(_passage_block(evidence.get(pid)))
    parts = report.get("sub_questions", [])
    trace.append({"step": "search",
                  "text": (f"Split the question into {len(parts)} parts and searched for each "
                           f"and for the whole question" if len(parts) > 1 else
                           "Searched VNIT's pages and documents")
                          + f": {len(first)} passages from "
                          + f"{len({r['source_url'] for r, _ in first})} sources."})
    for r, text in extra or []:
        pid, new = evidence.add(r, text, origin="corrective")
        if new:
            first_block.append(_passage_block(evidence.get(pid)))
    titles = tools.matching_titles(question,
                                   exclude=[p["result"]["source_url"] for p in evidence.passages])
    quality = (f"\n\nSearch quality: {search_grade['grade']} ({search_grade['why']})."
               if search_grade else "")
    messages = [
        {"role": "system", "content": system_prompt(schemas, steps_allowed, tokens_allowed, instructions)},
        {"role": "user", "content": f"{conversation}Student's question: {question}\n\nFirst search results:\n\n"
                                    + ("\n\n".join(first_block) or "(nothing found)")
                                    + f"\n\n{titles}{quality}"},
    ]

    answer, rounds, stale = "", 0, 0
    plan, done, cited, made = [], set(), set(), set()
    calculations, computed = [], []
    stop_reason = ""
    tools_on = planner.switched_on("AGENT_TOOLS") and bool(schemas)
    while tools_on and rounds < steps_allowed:
        _check_cancel(cancel)
        # Measured as planner.py does: the prompt, without the reply allowance.
        size = planner._estimate_tokens({"messages": messages, "tools": schemas})
        if size > planner.PROMPT_BUDGET and rounds:
            text, aside = compact(question, evidence, cited, conversation)
            messages = [messages[0], {"role": "user", "content": text + _status(plan, done, rounds,
                                                                                 steps_allowed,
                                                                                 tokens_allowed - llm.tokens)}]
            if aside:
                trace.append({"step": "compact", "text": f"Set {len(aside)} document(s) aside to stay "
                                                         "within the free tier's limit; I can reopen them."})
            size = planner._estimate_tokens({"messages": messages, "tools": schemas})
        if llm.tokens + size + REPLY_ESTIMATE > tokens_allowed:
            stop_reason = "budget"
            break
        try:
            message = llm.chat(messages, tools_on=True, schemas=schemas, extra=extras)
        except planner._ToolUseFailed:
            break
        content = strip_think(message.get("content") or "")
        cited |= set(re.findall(r"P\d+", content))
        calls = planner._tool_calls_of(message)
        if not calls:
            answer = content
            break
        if not plan:
            plan = parse_plan(content)
            if plan:
                trace.append({"step": "plan", "parts": plan,
                              "text": "Plan: " + " ".join(f"{i}. {p}" for i, p in enumerate(plan, 1))})
        done |= {n for n in parse_done(content) if 1 <= n <= len(plan)}

        rounds += 1
        calls = calls[:MAX_PARALLEL]
        messages.append({"role": "assistant", "content": message.get("content") or "",
                         "tool_calls": [c["raw"] for c in calls]})
        before, sums_before = len(evidence.passages), len(calculations)
        for c, result in zip(calls, _run_calls(calls, evidence, made)):
            if "value" in result:
                computed.append(result["value"])
                calculations.append(result["observation"])
            trace.append({"step": "tool", "tool": c["name"], "args": c["args"], "text": result["summary"]})
            messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"],
                             "content": result["observation"]})
        new = evidence.passages[before:]
        for i, part in enumerate(plan, 1):
            if i not in done and part_covered(part, new):
                done.add(i)
        stale = 0 if (new or len(calculations) > sums_before) else stale + 1
        if plan and len(done) >= len(plan):
            stop_reason = "plan done"
            break
        if stale >= STUCK_ROUNDS:
            stop_reason = "stuck"
            break
        open_parts = [p for i, p in enumerate(plan, 1) if i not in done]
        line = reflect(question, new, open_parts)
        trace.append({"step": "reflect", "text": line})
        messages.append({"role": "user", "content": line + _status(plan, done, rounds, steps_allowed,
                                                                   tokens_allowed - llm.tokens)})
    if rounds >= steps_allowed and not answer:
        stop_reason = stop_reason or "steps"
    if stop_reason:
        trace.append({"step": "stop", "text": STOP_NOTES[stop_reason]})

    _check_cancel(cancel)
    final, final_pids = final_messages(question, evidence, calculations, conversation, instructions)
    answer_pids = None if answer else final_pids
    live = LiveText(evidence, say)
    if not answer:
        answer = stream_text(llm, final, live.update, cancel) if emit else _plain(llm, final)
    elif emit:
        # Written during the loop, so there is nothing to stream: send it in words.
        raw = ""
        for piece in re.findall(r"\S+\s*", answer):
            raw += piece
            live.update(raw)
    if not answer:
        raise planner.AgentUnavailable("the model returned no answer")
    answer = _ascii_digits(answer)

    def shown(pids=None):
        return [f"{generate.passage_header(p['result'])} {p['text']}" for p in evidence.passages
                if pids is None or p["pid"] in pids]

    check = verifier.verify(planner._strip_labels(answer), shown(answer_pids), question, computed)
    trace.append({"step": "answer", "text": "Wrote the answer"
                  + (f" after {rounds} round(s) of tool use." if rounds else
                     " from the first search; no further lookups were needed.")})
    trace.append({"step": "verify", "text": verifier.summary(check), "verdict": check["verdict"]})

    if check["verdict"] == "unsupported":
        revision = final + [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": (
                "Verification: these figures in your answer do not appear in any passage: "
                f"{', '.join(check['unsupported'])}. Rewrite the answer using only figures that "
                "appear in the passages, or that are the visible result of a calculation you "
                "write out (e.g. 125000 × 4 = 500000). If you cannot support a figure, leave it "
                "out and say it was not found. Reply with the corrected answer only.")}]
        try:
            revised = _ascii_digits(_plain(llm, revision)) if planner.switched_on("VERIFY_REVISE") else ""
        except planner.AgentUnavailable:
            revised = ""
        if revised:
            recheck = verifier.verify(planner._strip_labels(revised), shown(final_pids), question, computed)
            trace.append({"step": "revise", "verdict": recheck["verdict"],
                          "text": "Rewrote the answer after the check. " + verifier.summary(recheck)})
            answer, check = revised, recheck
            say("replace", planner._citations_to_sources(answer, evidence)[0])
        if check["verdict"] == "unsupported":
            answer += ("\n\nNote: I could not confirm "
                       f"{', '.join(check['unsupported'])} in VNIT's documents, so please check "
                       "the linked source before relying on it.")

    text, sources, cited_pids, unknown = planner._citations_to_sources(answer, evidence)
    if unknown:
        trace.append({"step": "verify", "verdict": "citation",
                      "text": f"Removed citations to passages that were never shown ({', '.join(unknown)})."})
    return {
        "answer": text,
        "sources": sources,
        "mode": f"agent v2 ({model})",
        "trace": list(trace),
        "verification": check,
        "usage": {"llm_calls": llm.calls, "tokens": llm.tokens,
                  "waited_for_quota_s": round(llm.waited, 1),
                  "tool_calls": sum(1 for t in trace if t["step"] == "tool"),
                  "steps": rounds, "plan_parts": len(plan), "plan_done": len(done),
                  "budget": tokens_allowed,
                  "passages_seen": len(evidence.passages), "passages_cited": len(set(cited_pids))},
    }


STOP_NOTES = {
    "plan done": "Every part of the plan is found, so I stopped searching.",
    "budget": "Stopped searching to stay within this question's token budget.",
    "stuck": "Two rounds in a row found nothing new, so I stopped searching.",
    "steps": "Used every round of tools allowed for one question, so I stopped searching.",
}


def _status(plan, done, rounds, steps_allowed, tokens_left) -> str:
    parts = ""
    if plan:
        parts = " Plan: " + ", ".join(f"{i} {'done' if i in done else 'open'}"
                                      for i in range(1, len(plan) + 1)) + "."
    return (f"{parts} Steps left: {max(0, steps_allowed - rounds)}; about "
            f"{max(0, tokens_left):,} tokens left.")


_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _ascii_digits(text: str) -> str:
    """Devanagari digits as 0-9, so a Hindi or Marathi answer's figures can be verified."""
    return (text or "").translate(_DEVANAGARI_DIGITS)
