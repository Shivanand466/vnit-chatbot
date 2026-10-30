"""
The agent: decide what to look up, look it up, answer, then check the answer.

Before this module, every lookup followed one fixed recipe: split the
question, search once, hand the passages to the LLM, print whatever came back.
When that one search missed, the chatbot could only say "not found", and
nothing checked the answer it did give. This is the planner and verifier that
README.md listed as the missing agentic layer:

    observe   the first search runs as before (agent.answer: split, search each
              part and the whole question) -- the measured, tuned pipeline is
              the agent's first observation, not something it replaces;
    decide    the LLM reads those passages and chooses: answer now, or act;
    act       call tools (tools.py): search again with other words, find a
              document by title and look inside it, or calculate -- up to
              MAX_TOOL_ROUNDS rounds, each observing what the last one found;
    answer    write the answer citing the passages used ([P3]);
    verify    check every figure, date, email and phone number against the
              passages actually shown (verifier.py), with no LLM involved;
    revise    if something is unsupported, the model gets one chance to fix
              it; if it cannot, the answer carries a visible warning.

Every step is recorded in a `trace` that the chat page shows under "How I
found this", so the agent's decisions can be inspected rather than trusted.

Budget. Groq's free tier allows 8,000 tokens a minute; one answer with seven
passages is ~2,500. Most questions are answered from the first search in one
call -- the same cost as before. A question that needs tools costs one more
call per round, so rounds are capped, tool passages are shorter than the first
search's, and a passage already shown is referred to by label only. A 429
"rate limited" reply is waited out once when Groq says the wait is short.

If anything here fails (no key, no network, quota spent), respond.py falls
back to the one-shot pipeline (generate.llm_answer) on the same search
results, so the agent can make an answer better but never makes it worse
than it was.
"""
import json
import os
import re
import time
from datetime import date

import generate
import tools
import verifier

MAX_TOOL_ROUNDS = 2        # rounds of tool calls before the agent must answer
MAX_CALLS_PER_ROUND = 2    # tool calls honoured from one model reply
MAX_RATE_LIMIT_WAIT = 30   # seconds; a longer wait falls back instead

# Largest prompt (in estimated tokens, reply allowance excluded) the agent
# sends while it may still use tools. Past this, it stops searching and
# answers: a prompt plus its reply allowance must fit in one minute's 8,000.
PROMPT_BUDGET = 6000
# Passage text in the clean final-answer prompt (~4,000 tokens).
FINAL_CONTEXT_CHARS = 12000

# Room for reasoning plus a 120-word answer. Not more: Groq counts the
# *requested* max_tokens against the 8,000-a-minute allowance up front, so at
# 2,000 one question with a tool round used up the minute and the next
# question was refused (measured: 2,253 tokens left after a 72-token call).
# A reply cut off mid-reasoning comes back empty and is retried thinking less.
MAX_TOKENS = 1200


class AgentUnavailable(Exception):
    """The LLM could not be used; the caller should fall back."""


class _ToolUseFailed(Exception):
    """The model produced a tool call Groq could not accept."""


def _system_prompt() -> str:
    return (
        "You are the VNIT Nagpur student helpdesk agent. You answer students' questions "
        "about VNIT using only passages from VNIT's own website and documents, which you "
        f"get with your tools. Today's date is {date.today():%d %B %Y}.\n\n"
        "The results of a first search are already in the conversation. Each passage is "
        "labelled like [P3 · doc S57]: P3 is the passage, S57 the page or document it "
        "comes from.\n\n"
        "Decide what to do:\n"
        "- If the passages answer the question, answer straight away. Do not call tools "
        "you do not need.\n"
        "- If they do not, act before giving up: search_vnit with other words (the words a "
        "notice, fee sheet or calendar would use); or find_documents to locate the "
        "document that should hold the answer and read_document to search inside it; or "
        "calculate for any total or difference. You can call several tools at once.\n"
        "- If a document you opened does not hold the answer, do not search it again: use "
        "find_documents to see which other pages exist. Headline figures (totals, counts, "
        "who holds a post) are often on a section's own web page (Training & Placement, "
        "Hostel, Academics) rather than in a report.\n"
        f"- You have at most {MAX_TOOL_ROUNDS} rounds of tool calls. If the material still "
        "does not answer the question, say so plainly -- never guess.\n\n"
        "Cite the passages you used by their label right after each fact, like [P3]. "
        "Cite only passages you were shown.\n\n"
        f"{generate.ANSWER_GUIDE}"
    )


def _final_prompt(question: str, evidence: tools.Evidence, calculations):
    """A clean prompt for writing the answer: every passage found, no tool history.

    Returns (messages, ids of the passages it holds), so the answer can be
    verified against exactly what this prompt showed.

    Used when the agent has finished acting. With the tool calls still in the
    conversation, gpt-oss kept calling tools even when none were offered, and
    Groq refused every reply (400 tool_use_failed). Laid out as one prompt,
    there is nothing to imitate.

    Passages are kept within FINAL_CONTEXT_CHARS: the first search's top three,
    then what the tools found (it was looked for on purpose), then the rest.
    """
    first = [p for p in evidence.passages if p.get("origin") == "first"]
    found = [p for p in evidence.passages if p.get("origin") != "first"]
    blocks, used, pids = [], 0, set()
    for p in first[:3] + found + first[3:]:
        block = (f"[{p['pid']} · doc {tools.doc_id(p['result']['source_url'])}] "
                 f"{generate.passage_header(p['result'])[1:-1]}\n{p['text']}")
        if used + len(block) > FINAL_CONTEXT_CHARS and blocks:
            continue
        blocks.append(block)
        used += len(block)
        pids.add(p["pid"])
    calc = ("\n\nCalculations already done (exact):\n" + "\n".join(calculations)) if calculations else ""
    system = (
        "You are the VNIT Nagpur student helpdesk agent. You answer students' questions "
        "about VNIT using only passages from VNIT's own website and documents. Today's date "
        f"is {date.today():%d %B %Y}.\n\n"
        "The passages below are everything found by searching for this question; searching "
        "is finished. Each is labelled like [P3 · doc S57]. Answer now, citing the passages "
        "you used by their label right after each fact, like [P3]. Cite only these passages.\n\n"
        f"{generate.ANSWER_GUIDE}"
    )
    passages = "\n\n".join(blocks)
    user = f"Passages:\n\n{passages}{calc}\n\nStudent's question: {question}\n\nAnswer:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], pids


class _Pacer:
    """Wait for the per-minute token allowance instead of running into it.

    Groq refills the allowance continuously (8,000 a minute is ~133 a second)
    and reports what is left in each response's headers. A tool round's second
    call carries the first search, the tool results and the reply allowance --
    ~5,500 tokens after a ~4,200-token first call -- so without pacing nearly
    every question that used a tool was refused with a 429, and fell back.
    Waiting the few seconds the refill needs is better than giving up.
    """

    def __init__(self):
        self.limit = int(os.environ.get("GENAI_TOKENS_PER_MINUTE", "8000"))
        self.remaining = None
        self.at = 0.0

    def update(self, headers):
        try:
            self.remaining = int(headers.get("x-ratelimit-remaining-tokens"))
            self.limit = int(headers.get("x-ratelimit-limit-tokens") or self.limit)
            self.at = time.time()
        except (TypeError, ValueError):
            pass

    def wait_for(self, tokens_needed: int) -> float:
        """Sleep until `tokens_needed` fit, at most MAX_RATE_LIMIT_WAIT. Returns seconds slept."""
        if self.remaining is None:
            return 0.0
        rate = self.limit / 60.0
        available = min(self.limit, self.remaining + (time.time() - self.at) * rate)
        if tokens_needed <= available:
            return 0.0
        wait = min(MAX_RATE_LIMIT_WAIT, (tokens_needed - available) / rate + 0.5)
        time.sleep(wait)
        return wait


# One pacer per model, shared by every question in the process: Groq's
# allowance belongs to the API key and the model, not to one question.
_pacers = {}


def _pacer_for(model: str) -> _Pacer:
    return _pacers.setdefault(model, _Pacer())


def wait_for_quota(tokens: int, model: str = None) -> float:
    """Let another LLM caller (the one-shot fallback) wait for its model's allowance too."""
    return _pacer_for(model or os.environ.get("GENAI_MODEL", "openai/gpt-oss-20b")).wait_for(tokens)


def _estimate_tokens(payload) -> int:
    # ~3 characters a token for this mix of English, numbers and tables
    # (measured: 9,669 + 1,860 characters -> 2,962 prompt tokens), plus the
    # reply allowance, which Groq counts up front.
    return int(len(json.dumps(payload, ensure_ascii=False)) / 3.0) + payload.get("max_tokens", 0)


class _LLM:
    """A small OpenAI-compatible chat client that counts calls, tokens and waits."""

    def __init__(self, api_key, base_url, model):
        self.api_key, self.base_url, self.model = api_key, base_url, model
        self.calls = 0
        self.tokens = 0
        self.waited = 0.0

    def chat(self, messages, tools_on=True):
        import requests

        payload = {"model": self.model, "messages": messages, "max_tokens": MAX_TOKENS,
                   "temperature": 0}
        if tools_on:
            payload["tools"] = tools.SCHEMAS
            payload["tool_choice"] = "auto"
        attempts = 0
        while True:
            attempts += 1
            self.waited += _pacer_for(self.model).wait_for(_estimate_tokens(payload))
            resp = requests.post(f"{self.base_url}/chat/completions",
                                 headers={"Authorization": f"Bearer {self.api_key}"},
                                 json=payload, timeout=45)
            self.calls += 1
            _pacer_for(self.model).update(resp.headers)
            if resp.status_code == 429 and _is_daily_limit(resp):
                raise AgentUnavailable("the free AI daily allowance is used up (429); it refills "
                                       "gradually over 24 hours")
            if resp.status_code == 429 and attempts <= 3:
                wait = _retry_after(resp)
                if wait is not None and wait <= MAX_RATE_LIMIT_WAIT:
                    time.sleep(wait + 0.5)
                    self.waited += wait + 0.5
                    continue
            # Groq answers 400 "tool_use_failed" when the model wrote a malformed
            # tool call, or called one when it was not offered any -- gpt-oss
            # was trained with a browsing tool and sometimes reaches for it
            # ("read_document" with "cursor"/"loc" arguments, seen live).
            # Retrying the same conversation repeats the mistake, so the caller
            # switches to a clean prompt instead.
            if resp.status_code == 400 and "tool_use_failed" in resp.text:
                raise _ToolUseFailed()
            if resp.status_code == 429:
                raise AgentUnavailable("the free AI quota is busy (429), try again in a minute")
            if resp.status_code >= 400:
                # Status only: the error body can carry account details.
                raise AgentUnavailable(f"the AI service returned an error ({resp.status_code})")
            body = resp.json()
            self.tokens += body.get("usage", {}).get("total_tokens", 0)
            message = body["choices"][0]["message"]
            # A reasoning model can spend its budget thinking and return nothing
            # (generate.py, EXPERIMENTS-LOG §18c): retry once thinking less.
            if not (message.get("content") or "").strip() and not message.get("tool_calls") \
                    and "reasoning_effort" not in payload:
                payload["reasoning_effort"] = "low"
                continue
            return message


def _retry_after(resp):
    """Seconds Groq asks us to wait, from the header or the error text.

    The text reads "try again in 7.5s" or "try again in 12m3.2s"; reading only
    the seconds turned a 12-minute daily-limit wait into 3.2s and a retry.
    """
    header = resp.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)?s?", resp.text)
    if not m or not any(m.groups()):
        return None
    hours, minutes, seconds = (float(g) if g else 0.0 for g in m.groups())
    return hours * 3600 + minutes * 60 + seconds


def _is_daily_limit(resp) -> bool:
    """Groq's per-day allowance ("tokens per day (TPD)"), as opposed to per minute."""
    return "per day" in resp.text.lower() or "(tpd)" in resp.text.lower() or "(rpd)" in resp.text.lower()


def _citations_to_sources(answer: str, evidence: tools.Evidence):
    """Turn [P3]-style labels into [1], [2] numbered by the sources list.

    Returns (answer with numbered citations, sources, cited passage ids, unknown labels).
    Only pages and documents the answer actually cites are listed as sources;
    if it cites none, every page shown is listed, as the one-shot path does --
    unless the answer says the material does not cover the question, where
    listing pages would suggest they say something they do not.
    """
    sources, number_of_url, cited, unknown = [], {}, [], []

    def number_for(pid):
        p = evidence.get(pid)
        if p is None:
            unknown.append(pid)
            return None
        cited.append(pid)
        url = p["result"]["source_url"]
        if url not in number_of_url:
            sources.extend(generate.sources_of([p["result"]]))
            number_of_url[url] = len(sources)
        return number_of_url[url]

    def replace(m):
        numbers = []
        for pid in re.findall(r"P\d+", m.group(0)):
            n = number_for(pid)
            if n is not None and n not in numbers:
                numbers.append(n)
        return "".join(f"[{n}]" for n in numbers)

    # [P3], [P3, P5], [P3][P5], and the full-width brackets some models emit.
    text = re.sub(_LABELS, replace, answer)
    text = re.sub(r"【[^】]{0,40}】", "", text)                # stray markers ("【commentary】")
    text = re.sub(r"(\[\d+\])(?:\s*\1)+", r"\1", text)        # [1][1] -> [1]
    text = re.sub(r"\n\s*((?:\[\d+\])+)\s*(?=\n|$)", r" \1", text)  # a line of only citations
    text = re.sub(r"[ \t]+([.,;:])", r"\1", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    if not sources and not verifier.is_refusal(text):
        sources = generate.sources_of(p["result"] for p in evidence.passages)
    return text.strip(), sources, cited, unknown


def _tool_calls_of(message):
    calls = []
    for c in message.get("tool_calls") or []:
        fn = c.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": c.get("id", ""), "name": fn.get("name", ""), "args": args,
                      "raw": c})
    return calls


def run(question: str, report: dict, api_key: str = None, base_url: str = None,
        model: str = None) -> dict:
    """Answer `question` agentically, starting from the first search `report` (agent.answer).

    Returns answer, sources, mode, trace, verification and usage. Raises
    AgentUnavailable when the LLM cannot be used at all.
    """
    api_key = api_key or os.environ.get("GENAI_API_KEY")
    base_url = base_url or os.environ.get("GENAI_BASE_URL", "https://api.groq.com/openai/v1")
    # The agent runs on its own model, by default the larger gpt-oss-120b, while
    # the one-shot fallback and the follow-up rewrite stay on GENAI_MODEL. Groq's
    # free daily allowance (~200,000 tokens) is per model: on 2026-10-30 a day
    # of testing spent gpt-oss-20b's, and with one model for everything the
    # fallback died with the agent. On separate models, it still answers.
    model = model or os.environ.get("AGENT_MODEL", "openai/gpt-oss-120b")
    if not api_key:
        raise AgentUnavailable("no GENAI_API_KEY set")

    llm = _LLM(api_key, base_url, model)
    evidence = tools.Evidence()
    trace = []
    computed = []

    # Observe: the tuned first search, exactly the passages the one-shot path sends.
    first = generate.select_passages(report)
    first_block = []
    for r, text in first:
        pid, _ = evidence.add(r, text, origin="first")
        first_block.append(f"[{pid} · doc {tools.doc_id(r['source_url'])}] "
                           f"{generate.passage_header(r)[1:-1]}\n{text}")
    parts = report.get("sub_questions", [])
    trace.append({"step": "search",
                  "text": (f"Split the question into {len(parts)} parts and searched for each "
                           f"and for the whole question" if len(parts) > 1 else
                           "Searched VNIT's pages and documents")
                          + f": {len(first)} passages from "
                          + f"{len({r['source_url'] for r, _ in first})} sources."})

    titles = tools.matching_titles(question, exclude=[r["source_url"] for r, _ in first])
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": f"Student's question: {question}\n\nFirst search results:\n\n"
                                    + ("\n\n".join(first_block) or "(nothing found)")
                                    + f"\n\n{titles}"},
    ]

    # Decide and act, round by round. The model either answers (no tool calls)
    # or acts; after MAX_TOOL_ROUNDS, or when the conversation would no longer
    # fit the per-minute allowance, it writes the answer from a clean prompt.
    answer = ""
    rounds = 0
    calculations = []
    for _ in range(MAX_TOOL_ROUNDS):
        if _estimate_tokens({"messages": messages, "tools": tools.SCHEMAS}) > PROMPT_BUDGET:
            break
        try:
            message = llm.chat(messages, tools_on=True)
        except _ToolUseFailed:
            break
        calls = _tool_calls_of(message)
        if not calls:
            answer = (message.get("content") or "").strip()
            break

        rounds += 1
        calls = calls[:MAX_CALLS_PER_ROUND]
        messages.append({"role": "assistant", "content": message.get("content") or "",
                         "tool_calls": [c["raw"] for c in calls]})
        for c in calls:
            result = tools.run_tool(c["name"], c["args"], evidence)
            if "value" in result:
                computed.append(result["value"])
                calculations.append(result["observation"])
            trace.append({"step": "tool", "tool": c["name"], "args": c["args"],
                          "text": result["summary"]})
            messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"],
                             "content": result["observation"]})

    final, final_pids = _final_prompt(question, evidence, calculations)
    # An answer from the conversation saw every passage; one from the clean
    # prompt saw only what fitted in it.
    answer_pids = None if answer else final_pids
    if not answer:
        answer = _chat_text(llm, final)
    if not answer:
        raise AgentUnavailable("the model returned no answer")

    # Verify against exactly what the model was shown (headers carry document dates).
    def shown(pids=None):
        return [f"{generate.passage_header(p['result'])} {p['text']}" for p in evidence.passages
                if pids is None or p["pid"] in pids]

    check = verifier.verify(_strip_labels(answer), shown(answer_pids), question, computed)
    trace.append({"step": "answer", "text": "Wrote the answer"
                  + (f" after {rounds} round(s) of tool use." if rounds else
                     " from the first search; no further lookups were needed.")})
    trace.append({"step": "verify", "text": verifier.summary(check), "verdict": check["verdict"]})

    # Revise once if the check failed.
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
            revised = _chat_text(llm, revision)
        except AgentUnavailable:
            revised = ""
        if revised:
            recheck = verifier.verify(_strip_labels(revised), shown(final_pids), question, computed)
            trace.append({"step": "revise", "verdict": recheck["verdict"],
                          "text": "Rewrote the answer after the check. " + verifier.summary(recheck)})
            answer, check = revised, recheck
        if check["verdict"] == "unsupported":
            answer += ("\n\nNote: I could not confirm "
                       f"{', '.join(check['unsupported'])} in VNIT's documents, so please check "
                       "the linked source before relying on it.")

    text, sources, cited, unknown = _citations_to_sources(answer, evidence)
    if unknown:
        trace.append({"step": "verify", "verdict": "citation",
                      "text": f"Removed citations to passages that were never shown ({', '.join(unknown)})."})
    return {
        "answer": text,
        "sources": sources,
        "mode": f"agent ({model})",
        "trace": trace,
        "verification": check,
        "usage": {"llm_calls": llm.calls, "tokens": llm.tokens,
                  "waited_for_quota_s": round(llm.waited, 1),
                  "tool_calls": sum(1 for t in trace if t["step"] == "tool"),
                  "passages_seen": len(evidence.passages), "passages_cited": len(set(cited))},
    }


def _chat_text(llm: _LLM, messages) -> str:
    """The model's answer to a tool-free prompt, or AgentUnavailable."""
    try:
        return (llm.chat(messages, tools_on=False).get("content") or "").strip()
    except _ToolUseFailed:
        raise AgentUnavailable("the model kept calling tools instead of answering")


# [P3], [P3, P5], 【P3】, and [**P3**] (bold inside the brackets, seen live).
_LABELS = r"[\[【]\s*\**\s*P\d+(?:\s*[,;]\s*\**\s*P?\d+\**)*\s*\**\s*[\]】]"


def _strip_labels(answer: str) -> str:
    """The answer without [P3] labels, so a label number is never read as a figure."""
    return re.sub(_LABELS, " ", answer)
