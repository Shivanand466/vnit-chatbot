"""
Minimal API for the VNIT website chatbot pilot.

POST /ask {"question": "..."} -> retrieves, decomposes, and composes an
answer (LLM if GENAI_API_KEY is set and reachable, extractive otherwise).

Run:
    cd vnit-chatbot
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Then:
    curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
         -d '{"question": "What is the fee for B.Tech and where can I find the hostel rules?"}'
"""
import os
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import agent
import generate


@asynccontextmanager
async def lifespan(app):
    # Load the index and the search/rerank models before accepting requests,
    # so the first real question isn't the slow one (~20s of model loading).
    try:
        agent.answer("warm up")
        print("Models loaded - chatbot ready.")
    except Exception as e:
        print(f"Warm-up skipped ({type(e).__name__}: {e}); first question will be slower.")
    yield


app = FastAPI(title="VNIT Website Chatbot", lifespan=lifespan)

FRONTEND = Path(__file__).parent.parent / "frontend" / "index.html"

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


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "?")


def _check_rate_limit(ip: str):
    now = time.time()
    hits = _recent[ip]
    while hits and now - hits[0] > 86400:
        hits.popleft()
    if len(hits) >= PER_DAY or sum(1 for t in hits if now - t < 60) >= PER_MINUTE:
        raise HTTPException(429, "Too many questions - please wait a minute and try again.")
    hits.append(now)


class Question(BaseModel):
    question: str


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
    report = agent.answer(question)
    composed = generate.compose_answer(report)
    return {
        "question": question,
        "answer": composed["answer"],
        "sources": composed["sources"],
        "mode": composed["mode"],
        "sub_questions": [sq["sub_question"] for sq in report["sub_questions"]],
    }
