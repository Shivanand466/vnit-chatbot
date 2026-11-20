"""
A pretend LLM for trying the chat page without spending any Groq allowance.

Started with AGENT_FAKE_LLM=on (api/main.py), it stands in for Groq: the real
search, tools, verifier, streaming and chat page all run, and only the model's
replies are made up here, in code, from the passages the agent was shown. It
plans, calls a search tool once, then answers by quoting the best passage with
its citation; compare questions get a table, drafts a short letter, and the
reply streams word by word like the real one.

It is for screenshots and demos of the interface, never for measuring answer
quality, and it is off unless that switch is set. Answers in this mode carry
the mode "agent v2 (fake-llm)", so they can't be mistaken for real ones.
"""
import json
import re
import time

MODEL = "fake-llm"
_WORD_DELAY = 0.03


class _Response:
    def __init__(self, body=None, lines=None):
        self.status_code = 200
        self._body = body or {}
        self._lines = lines or []
        self.text = json.dumps(self._body)
        self.headers = {"x-ratelimit-remaining-tokens": "8000", "x-ratelimit-limit-tokens": "8000"}

    def json(self):
        return self._body

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            if line.startswith("data:") and '"content"' in line:
                time.sleep(_WORD_DELAY)
            yield line

    def close(self):
        pass


def _message(content="", tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}], "usage": {"total_tokens": 900}}


_PASSAGE = re.compile(r"\[(P\d+) · doc [^\]]*\] ([^\n]*)\n([^\[]+)", re.S)


def _passages(text):
    return [(pid, header, body.strip()) for pid, header, body in _PASSAGE.findall(text)]


def _question(text):
    m = re.search(r"(?:Student's question|Latest question): (.+)", text)
    return m.group(1).strip() if m else ""


def _best(passages, question, n=2):
    words = set(re.findall(r"[a-z]{4,}", question.lower()))
    scored = sorted(passages, key=lambda p: -len(words & set(re.findall(r"[a-z]{4,}", p[2].lower()))))
    return scored[:n]


def _sentence(body, limit=220):
    body = re.sub(r"\s+", " ", body)
    return body[:limit].rsplit(" ", 1)[0] + ("..." if len(body) > limit else "")


def _title(header):
    return header.split(" — ")[0].strip()


def _answer(system, user):
    """A reply built only from the passages shown, in the shape the task asks for."""
    question = _question(user)
    passages = _passages(user)
    if not passages:
        return "I couldn't find this in VNIT's documents."
    best = _best(passages, question)
    if "markdown table" in system:
        rows = "\n".join(f"| {_title(h)} | {_sentence(b, 90)} [{pid}] |" for pid, h, b in best)
        return f"Here is what the documents say:\n\n| Item | What the document says |\n|---|---|\n{rows}"
    if "Draft" in system:
        email = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", " ".join(b for _p, _h, b in passages))
        pid = next((p for p, _h, b in passages if email and email.group(0) in b), best[0][0])
        to = f"To: {email.group(0)} [{pid}]\n\n" if email else ""
        return (f"Draft — check before sending.\n\n{to}Subject: Request about {question[:60]}\n\n"
                "Dear Sir/Madam,\n\nI am writing to request your help with the matter above. "
                "I would be grateful for your guidance.\n\nYours sincerely,\n[Your name]\n[Roll number]")
    if "numbered steps" in system:
        return "\n".join(f"{i}. {_sentence(b, 140)} [{pid}]" for i, (pid, _h, b) in enumerate(best, 1))
    pid, header, body = best[0]
    lines = [f"According to **{_title(header)}**: {_sentence(body)} [{pid}]"]
    if len(best) > 1:
        lines.append(f"- Also: {_sentence(best[1][2], 140)} [{best[1][0]}]")
    if "Hindi" in system and "Devanagari" in system:
        lines.insert(0, "दस्तावेज़ों के अनुसार:")
    return "\n".join(lines)


def _reply(payload):
    messages = payload.get("messages", [])
    system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    user = "\n".join(m.get("content") or "" for m in messages if m["role"] == "user")
    if "Rewrite the student's latest question" in user:
        return _message(_question(user))
    if "General answer" in system:
        return _message("A general explanation would go here (fake LLM mode).")
    if payload.get("tools") and not any(m["role"] == "tool" for m in messages):
        question = _question(user)
        name, args = ("contact_office", {"topic": question}) if "Task: draft" in system else \
                     ("search_vnit", {"query": question})
        call = {"id": "fake1", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}
        return _message(f"1. Find what VNIT's documents say about: {question[:80]}", [call])
    return _message(_answer(system, user))


def _stream(body):
    text = body["choices"][0]["message"]["content"]
    lines = []
    for piece in re.findall(r"\S+\s*", text):
        lines.append("data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}))
    lines.append("data: " + json.dumps({"choices": [], "x_groq": {"usage": {"total_tokens": 900}}}))
    lines.append("data: [DONE]")
    return _Response(lines=lines)


def install():
    """Answer every chat-completions request with the pretend model, from now on."""
    import requests

    real = requests.post

    def post(url, **kw):
        if not str(url).endswith("/chat/completions"):
            return real(url, **kw)
        payload = kw.get("json") or {}
        body = _reply(payload)
        return _stream(body) if payload.get("stream") else _Response(body)

    requests.post = post
