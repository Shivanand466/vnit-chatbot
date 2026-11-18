"""
Minimal API for the VNIT website chatbot pilot.

POST /ask {"question": "...", "history": ["earlier question", ...]} ->
answers through respond.answer: the agent (planner.py) reads a first search,
may search again, open a document or calculate, and every figure in its answer
is checked against the sources (verifier.py). Without a key or quota it falls
back to a one-shot answer, then to quoting passages. `history` is optional; it
lets a follow-up like "and for girls?" be rewritten to stand on its own (see
followup.py), and the response says so in `understood_as`. `profile` is
optional too: details the student chose earlier (programme, gender, ...; see
slots.py), which fill in what a vague question leaves out. When a question
fits several groups' documents, the response has mode "clarify" and a
`clarify` object with choices for the chat page to show as buttons.

The response also carries `trace` (the steps taken, shown in the chat page as
"How I found this"), `verification` (the verifier's verdict) and, for agent
answers, `usage` (LLM calls, tokens, tool calls).

POST /feedback {"question": "...", "answer": "...", "rating": "up"|"down"}
appends one line to data/feedback/feedback.jsonl, so a demo week produces real
usage data instead of only self-written tests.

When the VNIT website demo has been built next to this repo
(../vnit-website/dist, see vnit-website/README.md), it is served at /site/,
with this chatbot as the floating VNIT Assistant on every page.

Run:
    cd vnit-chatbot
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Then:
    curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
         -d '{"question": "What is the fee for B.Tech and where can I find the hostel rules?"}'
"""
import json
import os
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import respond
import slots


@asynccontextmanager
async def lifespan(app):
    # Load the index and the search/rerank models before accepting requests,
    # so the first real question isn't the slow one (~20s of model loading).
    try:
        respond.warm_up()
        print("Models loaded - chatbot ready.")
    except Exception as e:
        print(f"Warm-up skipped ({type(e).__name__}: {e}); first question will be slower.")
    yield


app = FastAPI(title="VNIT Website Chatbot", lifespan=lifespan)

FRONTEND = Path(__file__).parent.parent / "frontend" / "index.html"
SITE = Path(__file__).parent.parent.parent / "vnit-website" / "dist"

if SITE.exists():
    @app.get("/site", include_in_schema=False)
    def site_root():
        return RedirectResponse("/site/")

    app.mount("/site", StaticFiles(directory=SITE, html=True), name="site")

# Which web pages may call this API from a browser. "*" is fine locally (the
# chat page may be opened as a file://). When deployed, the page is served by
# this same server (GET /), so set ALLOWED_ORIGINS to that site's address.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Per-visitor limits, so a public deployment can't be used to drain the free
# Groq quota behind it.
MAX_QUESTION_CHARS = 500
PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10"))
PER_DAY = int(os.environ.get("RATE_LIMIT_PER_DAY", "150"))
_recent = defaultdict(deque)

# How much of the conversation a follow-up may be resolved against. Three
# questions is enough for "and for girls?" while keeping the rewrite prompt
# small, and it bounds what a caller can push into it.
MAX_HISTORY = 3

# Ratings land here, one JSON object per line. Kept out of git (.gitignore):
# these are real students' questions, so they are the user's data, not the
# project's source.
FEEDBACK_PATH = Path(__file__).parent.parent / "data" / "feedback" / "feedback.jsonl"
MAX_COMMENT_CHARS = 1000


def _client_ip(request: Request) -> str:
    # Behind a Cloudflare tunnel every request arrives from 127.0.0.1; Cloudflare
    # puts the real visitor's address in CF-Connecting-IP (and overwrites any
    # value a visitor sends), so prefer it.
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "?")


def _check_rate_limit(ip: str, bucket: str = "ask"):
    now = time.time()
    hits = _recent[f"{bucket}:{ip}"]
    while hits and now - hits[0] > 86400:
        hits.popleft()
    if len(hits) >= PER_DAY or sum(1 for t in hits if now - t < 60) >= PER_MINUTE:
        raise HTTPException(429, "Too many questions - please wait a minute and try again.")
    hits.append(now)


class Question(BaseModel):
    question: str
    history: list[str] = []
    # What the student told the chat page (programme, gender, ...): kept in the
    # page only, sent with each question, and never stored here.
    profile: dict = {}


class Feedback(BaseModel):
    question: str
    answer: str = ""
    rating: str
    mode: str = ""
    comment: str = ""


@app.get("/")
def chat_page():
    return FileResponse(FRONTEND)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(q: Question, request: Request):
    question = q.question.strip()
    if not question:
        raise HTTPException(400, "Please type a question.")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Please keep questions under {MAX_QUESTION_CHARS} characters.")
    _check_rate_limit(_client_ip(request))

    # respond.answer owns the whole hierarchy: resolve a follow-up, decide what
    # kind of message this is, search only if it needs searching, then compose.
    history = [h.strip()[:MAX_QUESTION_CHARS] for h in q.history if h and h.strip()][-MAX_HISTORY:]
    return respond.answer(question, history, profile=slots.clean_profile(q.profile))


@app.post("/feedback")
def feedback(f: Feedback, request: Request):
    if f.rating not in ("up", "down"):
        raise HTTPException(400, "rating must be 'up' or 'down'.")
    if not f.question.strip():
        raise HTTPException(400, "feedback needs the question it refers to.")
    # A separate bucket: rating answers must not eat into someone's allowance
    # of questions, but it still can't be used to fill the disk.
    _check_rate_limit(_client_ip(request), bucket="feedback")

    record = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rating": f.rating,
        "question": f.question.strip()[:MAX_QUESTION_CHARS],
        "answer": f.answer.strip()[:2000],
        "mode": f.mode.strip()[:100],
        "comment": f.comment.strip()[:MAX_COMMENT_CHARS],
    }
    # No IP address is stored: who asked what is not needed to count how many
    # answers were useful.
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "saved", "thanks": True}
