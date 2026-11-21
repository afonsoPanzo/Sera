"""Sera API (SDD §9.1).

Run (from backend/):  uvicorn app.main:app --reload --port 8000
Docs:                 http://localhost:8000/docs
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, List, Literal, Optional

from dotenv import load_dotenv

# Explicit path: under `uvicorn --reload` the default lookup uses the cwd, not backend/.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import actions, agent, assistant, documents, voice  # noqa: E402
from .mission import router as mission_router  # noqa: E402
from .impact import analyze  # noqa: E402
from .models import (  # noqa: E402
    MISSION_TRANSITIONS, ApprovalRequest, ApprovalStatus, Document, Fact, ImpactReport, Mission,
    MissionStatus, MissionTask, Student, Verification, now,
)
from .store import DEMO_STUDENT_ID, new_id, store  # noqa: E402

app = FastAPI(title="Sera", version="0.1.0",
              description="Administrative intelligence for students. Demo student id: " + DEMO_STUDENT_ID)

app.include_router(mission_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- helpers ----------

def get_student(student_id: str) -> Student:
    s = store.students.get(student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    return s


def get_doc(doc_id: str) -> Document:
    d = store.documents.get(doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    return d


def get_mission(mission_id: str) -> Mission:
    m = store.missions.get(mission_id)
    if not m:
        raise HTTPException(404, "Mission not found")
    return m


def public_doc(d: Document) -> dict:
    """Never expose storage paths."""
    return d.model_dump(exclude={"storage_key"})


# ---------- health ----------

@app.get("/health")
def health():
    return {"status": "ok", "mock": agent.MOCK_MODE, "model": agent.OPENAI_MODEL}


# ---------- Sera chat (main endpoint for the frontend) ----------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class SimpleChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="The student's question")
    language: Literal["auto", "en", "hu"] = "auto"
    topic: Literal["general", "healthcare", "university", "immigration", "translation"] = "general"
    history: List[ChatMessage] = Field(default_factory=list, description="Previous turns, oldest first")


class Action(BaseModel):
    type: Literal["email_draft", "email", "call", "map", "link", "copy"]
    label: str
    href: Optional[str] = None   # mailto:, tel:, https://
    text: Optional[str] = None   # for "copy"


class SimpleChatResponse(BaseModel):
    reply: str
    language: Literal["en", "hu"]
    topic: str
    model: str
    mock: bool
    actions: List[Action] = Field(default_factory=list,
                                  description="Buttons the UI can offer; nothing is executed by the server")


@app.get("/api/topics")
def topics():
    """Topic buttons for the frontend, with example questions in EN and HU."""
    return assistant.TOPICS


@app.post("/api/chat", response_model=SimpleChatResponse)
def chat(body: SimpleChatRequest):
    try:
        result = assistant.answer(body.message, body.language, body.topic,
                                  [m.model_dump() for m in body.history],
                                  agent.OPENAI_API_KEY, agent.OPENAI_MODEL, agent.MOCK_MODE,
                                  agent.OPENAI_BASE_URL, agent.OPENAI_FALLBACK_MODELS)
    except Exception as e:  # never report a failed call as success
        raise ai_error(e)
    result["actions"] = actions.extract_actions(result["reply"], result["topic"], result["language"])
    return result


def ai_error(e: Exception) -> HTTPException:
    body = getattr(e, "body", None)
    code = body.get("code") if isinstance(body, dict) else None
    if code in ("insufficient_quota", "credit_balance_exhausted"):
        return HTTPException(503, "AI service unavailable: the AI account has no credits or quota left")
    if getattr(e, "status_code", None) == 503 or type(e).__name__ == "APITimeoutError":
        return HTTPException(503, "AI service is busy right now, please try again")
    return HTTPException(502, f"AI service error: {type(e).__name__}")


# ---------- Document Help ----------

class ExplainResponse(BaseModel):
    explanation: str
    document_type: str
    dates_found: List[str]
    truncated: bool
    language: Literal["en", "hu"]
    model: str
    mock: bool
    actions: List[Action] = Field(default_factory=list)


@app.post("/api/explain", response_model=ExplainResponse)
async def explain(file: Optional[UploadFile] = File(None), text: Optional[str] = Form(None),
                  language: Literal["en", "hu"] = Form("en")):
    """Explain a document in simple words. Send either a file (pdf/txt) or pasted text.
    Nothing is stored."""
    if file is not None and file.filename:
        content = await file.read()
        try:
            ext = documents.validate(file.filename, content)
        except documents.UploadError as e:
            raise HTTPException(400, str(e))
        doc_text, error = documents.extract_text(ext, content)
        if error:
            raise HTTPException(422, f"Could not read the document: {error}. Paste the text instead.")
    elif text and text.strip():
        doc_text = text
    else:
        raise HTTPException(422, "Send a file or paste the document text")
    if len(doc_text.strip()) < 20:
        raise HTTPException(422, "The document text is too short to explain")
    try:
        result = assistant.explain_document(doc_text, language, agent.OPENAI_API_KEY, agent.OPENAI_MODEL,
                                            agent.MOCK_MODE, agent.OPENAI_BASE_URL, agent.OPENAI_FALLBACK_MODELS)
    except Exception as e:
        raise ai_error(e)
    result["actions"] = actions.extract_actions(result["explanation"], "explain", language)
    return result


# ---------- Voice (ElevenLabs text-to-speech) ----------

class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Usually a Sera reply")
    language: Literal["en", "hu"] = "en"


@app.post("/api/speak", response_class=Response,
          responses={200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"}})
def speak(body: SpeakRequest):
    try:
        audio = voice.synthesize(body.text, body.language)
    except voice.VoiceNotConfigured as e:
        raise HTTPException(503, str(e))
    except voice.VoiceError as e:
        raise HTTPException(e.status, e.detail)
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


# ---------- students / digital twin ----------

@app.get("/api/students/{student_id}")
def student_twin(student_id: str):
    """The Administrative Digital Twin: profile + documents + missions."""
    s = get_student(student_id)
    return {
        "student": s,
        "documents": [public_doc(d) for d in store.student_documents(student_id)],
        "missions": store.student_missions(student_id),
    }


@app.get("/api/students/{student_id}/deadlines")
def deadlines(student_id: str, as_of: Optional[date] = None):
    get_student(student_id)
    today = as_of or date.today()
    out = []
    for m in store.student_missions(student_id):
        if m.deadline:
            out.append({"kind": "mission", "id": m.id, "title": m.title, "date": m.deadline,
                        "days_left": (m.deadline - today).days, "status": "confirmed"})
    for d in store.student_documents(student_id):
        f = d.expiry()
        if f.value:
            out.append({"kind": "document_expiry", "id": d.id, "title": d.title, "date": f.value,
                        "days_left": (f.value - today).days, "status": f.status.value})
    return sorted(out, key=lambda x: x["date"])


# ---------- documents ----------

@app.post("/api/students/{student_id}/documents", status_code=201)
async def upload_document(student_id: str, file: UploadFile = File(...), title: Optional[str] = Form(None)):
    get_student(student_id)
    content = await file.read()
    try:
        doc = documents.ingest(store, student_id, file.filename or "upload", content, title)
    except documents.UploadError as e:
        raise HTTPException(400, str(e))
    return public_doc(doc)


@app.get("/api/documents/{doc_id}")
def document_detail(doc_id: str):
    return public_doc(get_doc(doc_id))


class FactDecision(BaseModel):
    value: Optional[Any] = Field(None, description="Corrected value; omit to confirm the extracted one")
    decision: Literal["confirm", "reject"] = "confirm"


@app.post("/api/documents/{doc_id}/fields/{field}")
def decide_field(doc_id: str, field: str, body: FactDecision):
    """Student validates an extracted fact. Only this turns it into CONFIRMED."""
    doc = get_doc(doc_id)
    old = doc.fields.get(field)
    if old is None and body.value is None:
        raise HTTPException(404, "Field not found; provide a value to add it")
    value = body.value if body.value is not None else old.value
    if field.endswith("date") and isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            raise HTTPException(422, "Dates must be YYYY-MM-DD")
    status = Verification.CONFIRMED if body.decision == "confirm" else Verification.REJECTED
    doc.fields[field] = Fact(value=value, status=status, source=old.source if old else "user",
                             updated_by="user", updated_at=now())
    return public_doc(doc)


# ---------- missions ----------

class MissionCreate(BaseModel):
    title: str = Field(..., min_length=3)
    description: str = ""
    institution: str = ""
    deadline: Optional[date] = None
    depends_on: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)
    document_ids: List[str] = Field(default_factory=list, description="Documents that support this mission")
    completion_criteria: str = ""


@app.post("/api/students/{student_id}/missions", status_code=201)
def create_mission(student_id: str, body: MissionCreate):
    get_student(student_id)
    for mid in body.depends_on:
        get_mission(mid)
    for did in body.document_ids:
        if get_doc(did).student_id != student_id:
            raise HTTPException(403, "Document belongs to another student")
    m = Mission(id=new_id("mis"), student_id=student_id, title=body.title, description=body.description,
                institution=body.institution, deadline=body.deadline, depends_on=body.depends_on,
                tasks=[MissionTask(id=f"t{i+1}", title=t) for i, t in enumerate(body.tasks)],
                completion_criteria=body.completion_criteria)
    store.missions[m.id] = m
    return m


@app.get("/api/missions/{mission_id}")
def mission_detail(mission_id: str):
    m = get_mission(mission_id)
    missing = [r.description for r in m.requirements if not r.satisfied_by]
    return {"mission": m, "missing_requirements": missing,
            "progress": (sum(t.done for t in m.tasks) / len(m.tasks)) if m.tasks else None}


class StatusChange(BaseModel):
    status: MissionStatus


@app.post("/api/missions/{mission_id}/status")
def change_status(mission_id: str, body: StatusChange):
    m = get_mission(mission_id)
    if body.status not in MISSION_TRANSITIONS[m.status]:
        raise HTTPException(409, f"Cannot go from {m.status.value} to {body.status.value}")
    m.status = body.status
    return m


@app.post("/api/missions/{mission_id}/tasks/{task_id}")
def toggle_task(mission_id: str, task_id: str, done: bool = True):
    m = get_mission(mission_id)
    for t in m.tasks:
        if t.id == task_id:
            t.done = done
            return m
    raise HTTPException(404, "Task not found")


# ---------- impact ----------

class ImpactRequest(BaseModel):
    event: dict = Field(default_factory=lambda: {"type": "check"}, examples=[
        {"type": "check"},
        {"type": "document_expiry_change", "document_id": "doc-passport", "new_expiry_date": "2027-02-01"},
        {"type": "document_removed", "document_id": "doc-housing"},
    ])
    as_of: Optional[date] = None


@app.post("/api/students/{student_id}/impact", response_model=ImpactReport)
def impact(student_id: str, body: ImpactRequest):
    get_student(student_id)
    try:
        return analyze(store, student_id, body.event, body.as_of)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except (ValueError, TypeError) as e:
        raise HTTPException(422, f"Invalid event: {e}")


# ---------- approvals (human-in-the-loop) ----------

class ApprovalCreate(BaseModel):
    mission_id: Optional[str] = None
    action_type: Literal["send_email"] = "send_email"
    to: str
    subject: str
    body: str


@app.post("/api/students/{student_id}/approvals", status_code=201)
def request_approval(student_id: str, body: ApprovalCreate):
    get_student(student_id)
    if body.mission_id:
        get_mission(body.mission_id)
    a = ApprovalRequest(
        id=new_id("apr"), student_id=student_id, mission_id=body.mission_id, action_type=body.action_type,
        summary=f"Send an email to {body.to} with subject '{body.subject}'.",
        payload={"to": body.to, "subject": body.subject, "body": body.body},
    )
    store.approvals[a.id] = a
    return a


@app.get("/api/students/{student_id}/approvals")
def list_approvals(student_id: str):
    return [a for a in store.approvals.values() if a.student_id == student_id]


def execute(a: ApprovalRequest) -> None:
    """External action adapter. No real email provider yet: the result says so."""
    if a.action_type == "send_email":
        a.status = ApprovalStatus.SIMULATED
        a.result = "Demo mode: email was NOT actually sent. No email provider is configured."
    else:
        a.status = ApprovalStatus.FAILED
        a.result = f"Unknown action type {a.action_type}"


@app.post("/api/approvals/{approval_id}/{decision}")
def decide_approval(approval_id: str, decision: Literal["approve", "reject"]):
    a = store.approvals.get(approval_id)
    if not a:
        raise HTTPException(404, "Approval not found")
    if a.status != ApprovalStatus.PENDING:
        raise HTTPException(409, f"Approval already {a.status.value}")
    a.decided_at = now()
    if decision == "reject":
        a.status = ApprovalStatus.REJECTED
        return a
    a.status = ApprovalStatus.APPROVED
    execute(a)
    return a


# ---------- agent ----------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    language: Literal["auto", "en", "hu"] = "auto"
    history: List[ChatMessage] = Field(default_factory=list)


@app.post("/api/students/{student_id}/agent/chat")
def agent_chat(student_id: str, body: ChatRequest):
    get_student(student_id)
    try:
        return agent.chat(store, student_id, body.message, [m.model_dump() for m in body.history], body.language)
    except Exception as e:  # never report a failed call as success
        raise HTTPException(502, f"AI service error: {type(e).__name__}")
