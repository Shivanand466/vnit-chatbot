"""
Answer composition: turn agent.py's retrieved-and-decomposed passages into
a single readable answer.

UPDATE (2026-09-21, verified via RUNBOOK-FOR-CLAUDE-CODE.md): llm_answer()
below was confirmed working end-to-end on Shivanand's own machine, via
Groq, once run outside Claude's sandbox (whose egress proxy blocks
api.groq.com, openrouter.ai, api.together.xyz,
generativelanguage.googleapis.com, and api.openai.com -- confirmed
separately, and still true for Claude's own tool access). Three test
questions all came back with mode "llm (openai/gpt-oss-20b)" and correctly
composed, cited answers -- including correctly declining to answer when
the passages didn't cover the question, rather than guessing.

One real finding from that test: the model name that was hardcoded as the
default here (`llama-3.1-8b-instant`) had been retired from Groq's lineup
between when this file was written and when it was tested -- an API-side
change, not a bug. Default below is now `openai/gpt-oss-20b`, confirmed
live as of the test. Provider lineups change; if this default ever 404s
again with "model_not_found", check `GET {base_url}/models` for a current
one rather than assuming the code is broken.

UPDATE (2026-09-21, see REPORT2.md): the crawl-expansion round hit Groq
429 rate-limit errors on some questions. Root cause was chunk.py's chunking
bug (now fixed) producing oversized chunks -- sending two uncapped chunks
per sub-question could balloon past Groq's free-tier 8,000-tokens/minute
cap on its own. Even with chunking fixed, there's no reason to send more
context than the model needs, so context sent per chunk is now truncated
(MAX_CHUNK_CHARS) and the whole prompt has a hard ceiling (MAX_CONTEXT_CHARS)
as a second line of defense.
"""
import os
import re

# Per-chunk and total context caps for the LLM prompt -- see UPDATE above.
# ~150-word chunks are already ~800-900 chars; this only bites on outliers
# that slip through despite the chunk.py fix.
MAX_CHUNK_CHARS = 1000
MAX_CONTEXT_CHARS = 6000


def _is_document(url: str) -> bool:
    return "drive.google.com" in url or url.lower().endswith(".pdf")


def _first_sentences(text: str, n: int = 2, max_chars: int = 320) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    snippet = " ".join(sentences[:n]).strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rsplit(" ", 1)[0] + "..."
    return snippet


def compose_extractive(report: dict) -> dict:
    """No-LLM answer: stitch together the best passage per sub-question.
    Works fully offline -- this is what runs inside Claude's sandbox today."""
    answer_parts = []
    sources = []
    for sq in report["sub_questions"]:
        results = sq["results"]
        if not results:
            answer_parts.append(f"No good match found for: {sq['sub_question']}.")
            continue
        top = results[0]
        snippet = _first_sentences(top["text"], n=2)
        answer_parts.append(f"On \"{sq['sub_question']}\" — {top['title']} says: {snippet}")
        sources.append({"title": top["title"], "url": top["source_url"]})
        if sq["conflict_warning"]:
            answer_parts.append(f"(Note: {sq['conflict_warning']})")

    return {
        "answer": "\n\n".join(answer_parts),
        "sources": sources,
        "mode": "extractive",
    }


def llm_answer(report: dict, api_key: str = None, base_url: str = None, model: str = None) -> dict:
    """Compose a proper natural-language answer via an OpenAI-compatible chat
    completion endpoint (works with Groq, OpenRouter, Together, etc. -- any
    provider with an OpenAI-compatible /chat/completions route).

    Reads GENAI_API_KEY / GENAI_BASE_URL / GENAI_MODEL from the environment
    if not passed explicitly. Falls back to the extractive answer if no key
    is configured, or if the request fails for any reason (including the
    network restriction described at the top of this file) -- callers
    always get *an* answer back, with `mode` telling them which kind.
    """
    api_key = api_key or os.environ.get("GENAI_API_KEY")
    base_url = base_url or os.environ.get("GENAI_BASE_URL", "https://api.groq.com/openai/v1")
    model = model or os.environ.get("GENAI_MODEL", "openai/gpt-oss-20b")

    if not api_key:
        result = compose_extractive(report)
        result["mode"] = "extractive (no GENAI_API_KEY set)"
        return result

    # UPDATE (2026-09-21, see REPORT3.md): was sq["results"][:2] -- but
    # retrieve_for_subquestion() is called with k=3, and REPORT3.md's real
    # LLM tests found correct pages sitting at rank 3 that never made it
    # into the prompt because only the top 2 were ever sent. Now sends up to
    # 3 per sub-question; MAX_CONTEXT_CHARS below still caps total size, so
    # this doesn't reopen the 429 risk that top-2 was originally capping.
    context_blocks = []
    used_sources = []  # (title, url) actually included in context, in order, deduped
    seen_urls = set()
    seen_chunk_keys = set()  # (source_url, text[:80]) -- dedupe by actual chunk, not just page
    total_chars = 0

    def _add_chunk(r):
        nonlocal total_chars
        key = (r["source_url"], r["text"][:80])
        if key in seen_chunk_keys:
            return True  # already included, not a stop condition
        text = r["text"]
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS].rsplit(" ", 1)[0] + "..."
        dated = f" — dated {r['fetched']}" if r.get("fetched") and _is_document(r["source_url"]) else ""
        block = f"[{r['title']} — {r['source_url']}{dated}]\n{text}"
        if total_chars + len(block) > MAX_CONTEXT_CHARS and context_blocks:
            return False  # hard ceiling reached -- caller should stop adding
        context_blocks.append(block)
        total_chars += len(block)
        seen_chunk_keys.add(key)
        if r["source_url"] not in seen_urls:
            seen_urls.add(r["source_url"])
            used_sources.append({"title": r["title"], "url": r["source_url"],
                                 "date": r.get("fetched", "") if _is_document(r["source_url"]) else ""})
        return True

    # A compound question split into sub-questions can lose context that only
    # the whole question carries, so agent.py also retrieves for the undivided
    # question. Those chunks go in FIRST: added last, they lost the budget race
    # (measured: the placements-stats chunk was refused by 27 chars of a
    # 6000-char budget already filled by weaker sub-question chunks).
    for r in report.get("whole_question_results", [])[:3]:
        if not _add_chunk(r):
            break

    for sq in report["sub_questions"]:
        # Up to 5 per sub-question (MAX_CONTEXT_CHARS still caps the total).
        # With 3, a first-year calendar question got the right document but not
        # the "Commencement of Classes" line (4th-ranked chunk), and the LLM
        # answered from "Commencement of Next Session" instead -- a wrong answer.
        for r in sq["results"][:5]:
            if not _add_chunk(r):
                break

    context = "\n\n".join(context_blocks)

    prompt = (
        "Answer the student's question using ONLY the passages below. "
        "Cite the source title for every claim. If the passages don't cover "
        "part of the question, say so plainly instead of guessing.\n"
        "If a figure applies only to a particular group (e.g. a fee category like "
        "OPEN/OBC/EWS vs SC/ST/PwD, or a specific programme or year), say which "
        "group it applies to. If passages are dated documents that disagree, "
        "prefer the most recent one and mention its date.\n\n"
        f"Passages:\n{context}\n\nQuestion: {report['question']}\n\nAnswer:"
    )

    try:
        import requests
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        # UPDATE (2026-09-21, see REPORT3.md): sources used to be rebuilt from
        # sq["results"][0] (top-1 per sub-question) regardless of what was
        # actually sent to the LLM -- so it could name a page the model never
        # saw (REPORT3.md's Electrical/5G examples: sources named the civil
        # dept / convocation pages while the model was actually working from
        # different passages). `used_sources` is exactly the set of pages
        # whose text was included in the prompt above, so it can't drift
        # from what was actually cited from.
        return {"answer": text, "sources": used_sources, "mode": f"llm ({model})"}
    except Exception as e:
        result = compose_extractive(report)
        result["mode"] = f"extractive (LLM call failed: {e})"
        return result


def compose_answer(report: dict) -> dict:
    """Default entry point: tries the LLM path, transparently falls back to
    extractive if no key / no network."""
    return llm_answer(report)
