"""
House Of Wax — LiveAvatar backend service.

Separate FastAPI service (not part of the Streamlit app) that:
  - issues short-lived HeyGen streaming tokens, keeping HEYGEN_API_KEY off the browser
  - answers visitor questions with Claude, grounded in published Knowledge Hub content

Deploy this on its own (Railway/Render/etc), not on Streamlit Cloud — Streamlit
can't serve real-time endpoints to the embedded widget the way this needs.

Required environment variables:
  HEYGEN_API_KEY       HeyGen API key (Developers -> Overview -> Create API Key)
  ANTHROPIC_API_KEY    Anthropic API key (console.anthropic.com), separate from claude.ai
  SUPABASE_URL         Same Supabase project the main app uses
  SUPABASE_ANON_KEY    Same anon key the main app uses (read-only use here)

Optional:
  ALLOWED_ORIGIN        Origin allowed to call this service (your Streamlit app's URL).
                         Defaults to "*" for initial testing -- lock this down before
                         a public launch.
  LIVEAVATAR_ENABLED    "false" disables both endpoints immediately (a hard kill switch
                         independent of the app's own admin toggle). Defaults to "true".
"""
import os
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("ALLOWED_ORIGIN", "*")],
    allow_methods=["POST"],
    allow_headers=["*"],
)

HEYGEN_API_KEY = os.environ["HEYGEN_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

MAX_QUESTION_LENGTH = 400
CONTEXT_CACHE_SECONDS = 900  # 15 minutes

PERSONA = """You are the voice of House Of Wax, a marketplace for vinyl records
and music collectibles. Answer visitor questions in a friendly, knowledgeable,
collector-to-collector tone. Only answer questions about House Of Wax, vinyl
grading, buying/selling on the marketplace, or general record-collecting topics.
If asked about anything else, politely steer the conversation back to House Of
Wax and collecting. Keep answers short -- 2-3 sentences -- since they'll be
spoken aloud by an avatar."""

_context_cache = {"text": "", "fetched_at": 0.0}


def enabled() -> bool:
    return os.environ.get("LIVEAVATAR_ENABLED", "true").lower() != "false"


async def knowledge_hub_context() -> str:
    """Pull a short summary of recently published Knowledge Hub posts, cached briefly."""
    if time.time() - _context_cache["fetched_at"] < CONTEXT_CACHE_SECONDS and _context_cache["text"]:
        return _context_cache["text"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/knowledge_posts",
                headers={"apikey": SUPABASE_ANON_KEY, "authorization": f"Bearer {SUPABASE_ANON_KEY}"},
                params={
                    "select": "title,summary",
                    "status": "eq.Published",
                    "order": "updated_at.desc",
                    "limit": "20",
                },
            )
            r.raise_for_status()
            posts = r.json()
        lines = [f"- {p['title']}: {p['summary']}" for p in posts if p.get("title")]
        text = "Recent House Of Wax Knowledge Hub articles:\n" + "\n".join(lines) if lines else ""
        _context_cache["text"] = text
        _context_cache["fetched_at"] = time.time()
        return text
    except Exception:
        # Knowledge Hub context is a nice-to-have; answer from the persona alone if it's unreachable.
        return _context_cache["text"]


class TokenResponse(BaseModel):
    token: str


@app.post("/get-token", response_model=TokenResponse)
async def get_token():
    if not enabled():
        raise HTTPException(503, "The avatar assistant is currently disabled.")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.heygen.com/v1/streaming.create_token",
            headers={"x-api-key": HEYGEN_API_KEY},
        )
        r.raise_for_status()
        data = r.json()
    return {"token": data["data"]["token"]}


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest):
    if not enabled():
        raise HTTPException(503, "The avatar assistant is currently disabled.")
    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "Empty question")
    if len(question) > MAX_QUESTION_LENGTH:
        question = question[:MAX_QUESTION_LENGTH]

    context = await knowledge_hub_context()
    system_prompt = PERSONA + ("\n\n" + context if context else "")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-5",
                    "max_tokens": 300,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": question}],
                },
            )
            r.raise_for_status()
            data = r.json()
        answer_text = "".join(
            block["text"] for block in data["content"] if block["type"] == "text"
        ).strip()
        if not answer_text:
            answer_text = "Sorry, I don't have a good answer for that one -- try asking about grading, buying, or selling on House Of Wax."
    except Exception as exc:
        print(f"[liveavatar_service] /ask failed: {exc}")
        answer_text = "Sorry, I'm having trouble answering right now -- try again in a moment."

    return {"answer": answer_text}
