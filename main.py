"""StudentMate AI — backend (FastAPI + OpenAI).

Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import os
from typing import List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from prompts import build_system_prompt

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# MOCK_MODE=1 (or no API key) returns fake answers so the frontend can integrate without a key.
MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1" or not OPENAI_API_KEY
MAX_HISTORY = 10  # last N messages sent to the model

client = None
if not MOCK_MODE:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="StudentMate AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Schemas ----------

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="The student's question")
    language: Literal["auto", "en", "hu"] = "auto"
    history: List[Message] = Field(default_factory=list, description="Previous turns, oldest first")


class ChatResponse(BaseModel):
    reply: str
    language: str
    model: str
    mock: bool


# ---------- Helpers ----------

def detect_language(text: str) -> str:
    """Very light Hungarian detector, used only to label the response for the frontend."""
    hu_chars = set("áéíóöőúüű")
    hu_words = {"és", "hogy", "nem", "egy", "vagy", "kell", "hol", "mit", "hogyan", "szeretnék", "köszönöm", "kérem"}
    t = text.lower()
    words = set(t.replace("?", " ").replace(",", " ").split())
    if sum(c in hu_chars for c in t) >= 2 or len(words & hu_words) >= 1:
        return "hu"
    return "en"


def mock_reply(message: str, lang: str) -> str:
    if lang == "hu":
        return (f"[MOCK] Ez egy tesztválasz erre a kérdésre: „{message}”. "
                "Az igazi választ az OpenAI API adja, amikor be van állítva az API kulcs.")
    return (f"[MOCK] This is a test answer to: \"{message}\". "
            "The real answer will come from the OpenAI API once the API key is set.")


# ---------- Routes ----------

@app.get("/health")
def health():
    return {"status": "ok", "mock": MOCK_MODE, "model": OPENAI_MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    reply_lang = req.language if req.language != "auto" else detect_language(req.message)

    if MOCK_MODE:
        return ChatResponse(reply=mock_reply(req.message, reply_lang), language=reply_lang,
                            model="mock", mock=True)

    messages = [{"role": "system", "content": build_system_prompt(req.language)}]
    messages += [m.model_dump() for m in req.history[-MAX_HISTORY:]]
    messages.append({"role": "user", "content": req.message})

    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=600,
        )
    except Exception as e:  # never report a failed call as a success
        raise HTTPException(status_code=502, detail=f"AI service error: {type(e).__name__}")

    reply = (completion.choices[0].message.content or "").strip()
    if not reply:
        raise HTTPException(status_code=502, detail="AI service returned an empty answer")

    return ChatResponse(reply=reply, language=reply_lang, model=OPENAI_MODEL, mock=False)
