"""Chatbot smoke test for the website, with no Groq key (so no LLM quota is used).

Expects the chatbot server already running on 127.0.0.1:8010, started from
vnit-chatbot without GENAI_API_KEY. Fetches /site/, then asks three demo
questions and the vague "What is the hostel fee?", which must come back as a
clarifying question with choices. Prints mode, number of sources and the start
of each answer. Exits with 1 if anything is wrong.
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8010"
QUESTIONS = [
    "Who is the current Director of VNIT?",
    "What is the email of the Dean (Academic)?",
    "When do classes start for first year B.Tech students in Winter 2026?",
]


def ask(question, profile=None):
    body = json.dumps({"question": question, "history": [], "profile": profile or {}}).encode()
    req = urllib.request.Request(BASE + "/ask", data=body, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ok = True
    page = urllib.request.urlopen(BASE + "/site/", timeout=30).read().decode("utf-8")
    has_widget = "vnit-assistant.js" in page and "Student project demo" in page
    print(f"GET /site/: {'ok, banner and widget script present' if has_widget else 'MISSING banner or widget'}")
    ok &= has_widget
    for q in QUESTIONS:
        d = ask(q)
        print(f"\nQ: {q}\n   mode: {d['mode']} | sources: {len(d.get('sources', []))}\n   answer: {d['answer'][:200]!r}")
        ok &= d["mode"].startswith("extractive") and bool(d.get("sources"))
    d = ask("What is the hostel fee?")
    choices = [c["label"] for c in (d.get("clarify") or {}).get("choices", [])]
    print(f"\nQ: What is the hostel fee?\n   mode: {d['mode']} | choices: {choices}\n   answer: {d['answer'][:200]!r}")
    ok &= d["mode"] == "clarify" and len(choices) >= 2
    print("\nsmoke test", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
