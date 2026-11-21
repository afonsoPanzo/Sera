"""StudentMate Agent — live demo mission: sick student -> Hungarian doctor call -> lecturer email.

Flow (all endpoints under /api):
  1. POST /chat-triage            English message -> name, symptoms, allergies, course + permission question
  2. POST /confirm-and-execute    student said yes -> ElevenLabs/Twilio outbound call to the doctor (Hungarian)
  3. POST /elevenlabs-webhook     post-call transcript -> appointment time -> bilingual email to lecturer
     POST /simulate-call-complete same as 3 without a real call (fallback if the venue has no signal)
  GET  /mission-status            live state for the UI (polling)
  POST /mission-reset             back to IDLE between rehearsals

Secrets come from backend/.env only (see .env.example). Nothing is reported as done unless it was:
a failed call or email shows CALL_FAILED / email.status = "failed".
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import smtplib
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["mission"])

OUTBOUND_URL = os.getenv("ELEVENLABS_OUTBOUND_URL", "https://api.elevenlabs.io/v1/convai/twilio/outbound-call")
DEFAULT_STUDENT = "Alex Vance"
DEFAULT_COURSE = "Algorithms & Data Structures"
FALLBACK_TIME = "14:30 CET"
E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ---------------------------------------------------------------- state

Status = Literal["IDLE", "TRIAGE_DONE", "CALLING_DOCTOR", "CALL_FAILED", "SENDING_EMAIL", "COMPLETED"]


class MissionState:
    """One live mission (the stage demo). Thread-safe, in memory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self.data: dict[str, Any] = {
                "status": "IDLE", "student": {}, "contacts": {}, "conversation_id": None, "call_sid": None,
                "appointment_time": None, "appointment_time_source": None, "transcript_excerpt": None,
                "email": {"status": "not_sent", "to": None, "sent_at": None, "error": None},
                "student_callback": {"status": "not_requested"}, "events": [],
            }

    def update(self, event: str | None = None, **changes: Any) -> None:
        with self._lock:
            for k, v in changes.items():
                if isinstance(v, dict) and isinstance(self.data.get(k), dict):
                    self.data[k] = {**self.data[k], **v}
                else:
                    self.data[k] = v
            if event:
                self.data["events"].append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                            "status": self.data["status"], "message": event})

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self.data, default=str))


mission = MissionState()


# ---------------------------------------------------------------- step 1: triage

SYMPTOMS = [  # (pattern, english, hungarian)
    (r"high fever|very high temperature", "high fever", "magas láz"),
    (r"(?<!high )\bfever\b|temperature", "fever", "láz"),
    (r"sore throat", "sore throat", "torokfájás"),
    (r"cough", "cough", "köhögés"),
    (r"headache|migraine", "headache", "fejfájás"),
    (r"vomit|throwing up", "vomiting", "hányás"),
    (r"nause", "nausea", "hányinger"),
    (r"diarrh", "diarrhoea", "hasmenés"),
    (r"stomach ?ache|abdominal pain", "stomach ache", "hasfájás"),
    (r"chills|shiver", "chills", "hidegrázás"),
    (r"dizz", "dizziness", "szédülés"),
    (r"runny nose|blocked nose", "runny nose", "orrfolyás"),
    (r"\bflu\b|influenza", "flu-like symptoms", "influenzaszerű tünetek"),
    (r"body aches?|muscle pain", "body aches", "izomfájdalom"),
    (r"short(ness)? of breath|can'?t breathe", "shortness of breath", "légszomj"),
]
ALLERGY_HU = {"penicillin": "penicillin", "amoxicillin": "amoxicillin", "aspirin": "aszpirin", "ibuprofen": "ibuprofen",
              "nuts": "dió", "peanuts": "földimogyoró", "lactose": "laktóz", "gluten": "glutén", "pollen": "pollen",
              "latex": "latex", "sulfa": "szulfonamid"}
EMERGENCY = re.compile(r"chest pain|can'?t breathe|unconscious|faint|seizure|bleeding heavily|suicid", re.I)


class TriageRequest(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    student_name: Optional[str] = None
    course_name: Optional[str] = None


def _join(items: list[str], conj: str) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {conj} " + items[-1]


def triage_rules(text: str) -> dict:
    t = text.lower()
    found = [(en, hu) for pat, en, hu in SYMPTOMS if re.search(pat, t)]
    if any(en == "high fever" for en, _ in found):
        found = [(en, hu) for en, hu in found if en != "fever"]
    allergies = []
    for m in re.finditer(r"allerg(?:ic|y)\s+(?:to\s+)?([a-z][a-z\- ]{2,30}?)(?=[,.;!]| and | but |$)", t):
        allergies.append(m.group(1).strip())
    for m in re.finditer(r"\b([a-z]+)\s+allergy", t):
        if m.group(1) not in ("an", "my", "food", "no", "any"):
            allergies.append(m.group(1))
    allergies = list(dict.fromkeys(a for a in allergies if a))
    name = None
    m = re.search(r"\b(?:my name is|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    if m and m.group(1).lower() not in ("sick", "allergic", "not", "unable"):
        name = m.group(1)
    course = None
    m = re.search(r"\b(?:attend|miss|skip)\s+(?:my\s+|the\s+)?([A-Z][\w&\- ]{2,50}?)\s+(?:class|lecture|seminar|lab)", text)
    if m:
        course = m.group(1).strip()
    return {
        "symptoms": [en for en, _ in found], "symptoms_hu": [hu for _, hu in found],
        "allergies": allergies, "allergies_hu": [ALLERGY_HU.get(a, a) for a in allergies],
        "student_name": name, "course_name": course,
        "misses_class": bool(re.search(r"can'?t attend|cannot attend|miss(ing)? (my |the )?class|won'?t (be able to )?come", t)),
        "emergency": bool(EMERGENCY.search(t)),
    }


@router.post("/chat-triage")
def chat_triage(body: TriageRequest):
    """Fast, deterministic extraction (no LLM latency on stage)."""
    r = triage_rules(body.message)
    student = body.student_name or r["student_name"] or DEFAULT_STUDENT
    course = body.course_name or r["course_name"] or DEFAULT_COURSE
    symptoms = _join(r["symptoms"], "and") if r["symptoms"] else "feeling unwell"
    symptoms_hu = _join(r["symptoms_hu"], "és") if r["symptoms_hu"] else "rossz közérzet"
    allergies = _join(r["allergies"], "and") if r["allergies"] else "none reported"
    allergies_hu = _join(r["allergies_hu"], "és") if r["allergies_hu"] else "nincs ismert allergia"

    if r["emergency"]:
        question = ("This sounds like it could be an emergency. Please call 112 now. "
                    "I will not book a normal appointment for this.")
    else:
        noted = f"I have noted your symptoms ({symptoms})"
        noted += f" and your {allergies} allergy." if r["allergies"] else "."
        email_part = (f" and notify your lecturer for {course} by email"
                      if (email_configured() or env("LECTURER_EMAIL")) else "")
        question = f"{noted} Should I call the campus doctor in Hungarian to book an appointment{email_part}?"

    result = {"student_name": student, "course_name": course, "symptoms": symptoms, "symptoms_hu": symptoms_hu,
              "allergies": allergies, "allergies_hu": allergies_hu, "misses_class": r["misses_class"],
              "emergency": r["emergency"], "confirmation_question": question, "needs_confirmation": not r["emergency"]}
    mission.reset()
    mission.update("Triage completed, waiting for the student's permission", status="TRIAGE_DONE",
                   student={k: result[k] for k in ("student_name", "course_name", "symptoms", "symptoms_hu",
                                                     "allergies", "allergies_hu")})
    return result


# ---------------------------------------------------------------- step 2: call the doctor

class ConfirmRequest(BaseModel):
    doctor_phone: str = Field(..., description="E.164, e.g. +36301234567")
    student_phone: Optional[str] = None
    lecturer_email: Optional[str] = Field(None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    student_name: str = DEFAULT_STUDENT
    course_name: str = DEFAULT_COURSE
    symptoms: str = Field(..., min_length=2, max_length=300)
    allergies: str = Field("none reported", max_length=200)
    preferred_window: str = Field("Ma 15:00 előtt", max_length=100)


def _clean_phone(p: str) -> str:
    return re.sub(r"[\s\-()]", "", p or "")


async def _place_call(to_number: str, variables: dict, agent_id: str) -> dict:
    import httpx

    key = env("ELEVENLABS_API_KEY")
    phone_id = env("ELEVENLABS_AGENT_PHONE_NUMBER_ID")
    if not key or not agent_id or not phone_id:
        raise HTTPException(503, "ElevenLabs call not configured: set ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID "
                                 "and ELEVENLABS_AGENT_PHONE_NUMBER_ID in backend/.env")
    payload = {"agent_id": agent_id, "agent_phone_number_id": phone_id, "to_number": to_number,
               "conversation_initiation_client_data": {"dynamic_variables": variables}}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(OUTBOUND_URL, headers={"xi-api-key": key}, json=payload)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Could not reach ElevenLabs: {type(e).__name__}")
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:300]}
    if r.status_code >= 300 or body.get("success") is False:
        detail = body.get("detail") or body.get("message") or body
        raise HTTPException(502, f"ElevenLabs rejected the call ({r.status_code}): {json.dumps(detail)[:300]}")
    return body


@router.post("/confirm-and-execute")
async def confirm_and_execute(body: ConfirmRequest):
    doctor = _clean_phone(body.doctor_phone)
    if not E164.match(doctor):
        raise HTTPException(422, "doctor_phone must be in international format, e.g. +36301234567")
    student_phone = _clean_phone(body.student_phone) if body.student_phone else None
    if student_phone and not E164.match(student_phone):
        raise HTTPException(422, "student_phone must be in international format, e.g. +36301234567")
    if mission.snapshot()["status"] == "CALLING_DOCTOR":
        raise HTTPException(409, "A call is already in progress. Wait for it or POST /api/mission-reset.")

    lecturer_email = body.lecturer_email or env("LECTURER_EMAIL") or None
    variables = {"student_name": body.student_name, "symptoms": body.symptoms,
                 "allergies": body.allergies, "preferred_window": body.preferred_window}
    mission.update("Student gave permission. Calling the doctor in Hungarian…", status="CALLING_DOCTOR",
                   student={"student_name": body.student_name, "course_name": body.course_name,
                            "symptoms": body.symptoms, "allergies": body.allergies},
                   contacts={"doctor_phone": doctor, "student_phone": student_phone,
                             "lecturer_email": lecturer_email, "preferred_window": body.preferred_window},
                   email={"to": lecturer_email})
    try:
        result = await _place_call(doctor, variables, env("ELEVENLABS_AGENT_ID"))
    except HTTPException as e:
        mission.update(f"Call failed: {e.detail}", status="CALL_FAILED")
        raise
    conv = result.get("conversation_id")
    mission.update(f"Call started (conversation {conv or 'unknown'}). Waiting for the doctor…",
                   conversation_id=conv, call_sid=result.get("callSid") or result.get("call_sid"))
    return {"status": "CALLING_DOCTOR", "conversation_id": conv, "elevenlabs": result}


# ---------------------------------------------------------------- step 3: after the call

HU_NUM = {"egy": 1, "kettő": 2, "két": 2, "három": 3, "négy": 4, "öt": 5, "hat": 6, "hét": 7, "nyolc": 8,
          "kilenc": 9, "tíz": 10, "tizenegy": 11, "tizenkettő": 12, "tizenkét": 12}
_W = "|".join(sorted(HU_NUM, key=len, reverse=True))


def _fmt(h: int, m: int, pm_hint: bool) -> Optional[str]:
    if pm_hint and h < 12:
        h += 12
    if 0 <= h <= 23 and 0 <= m <= 59:
        return f"{h:02d}:{m:02d} CET"
    return None


def times_in(text: str) -> list[str]:
    """All clock times mentioned in a text (Hungarian or English), in order."""
    found: list[tuple[int, str]] = []
    pm = bool(re.search(r"délután|du\.|\bpm\b|afternoon|este", text, re.I))
    for m in re.finditer(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b(?!\s*(?:Ft|HUF|%))", text):
        t = _fmt(int(m.group(1)), int(m.group(2)), pm and int(m.group(1)) < 8)
        if t:
            found.append((m.start(), t))
    for m in re.finditer(rf"\bfél\s+({_W}|\d{{1,2}})(?:re|ra|kor)?\b", text, re.I):   # "fél három(ra)" = 2:30
        w = m.group(1).lower()
        h = HU_NUM.get(w) or int(w)
        t = _fmt(h - 1, 30, pm or h - 1 < 8)
        if t:
            found.append((m.start(), t))
    for m in re.finditer(rf"\b({_W}|\d{{1,2}})\s*(?:óra(?:kor)?|órára)\b(?:\s*(\d{{1,2}})\s*perc)?", text, re.I):
        w = m.group(1).lower()
        h = HU_NUM.get(w) or int(w)
        t = _fmt(h, int(m.group(2) or 0), pm or h < 8)
        if t:
            found.append((m.start(), t))
    for m in re.finditer(r"\b(\d{1,2})\s*(am|pm)\b", text, re.I):
        h = int(m.group(1)) % 12 + (12 if m.group(2).lower() == "pm" else 0)
        found.append((m.start(), f"{h:02d}:00 CET"))
    return [t for _, t in sorted(found)]


def extract_appointment(payload: dict) -> tuple[str, str, str]:
    """Returns (time, source, excerpt). source: data_collection | transcript | fallback."""
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    analysis = data.get("analysis") or {}
    for key, item in (analysis.get("data_collection_results") or {}).items():
        if re.search(r"time|idopont|időpont|appointment", key, re.I):
            value = item.get("value") if isinstance(item, dict) else item
            if value:
                ts = times_in(str(value))
                return (ts[-1] if ts else str(value)), "data_collection", str(value)
    turns = data.get("transcript") or []
    lines = [f"{t.get('role', '?')}: {t.get('message') or ''}" for t in turns if isinstance(t, dict)]
    text = "\n".join(lines)
    ts = times_in(text)
    if ts:
        return ts[-1], "transcript", "\n".join(lines[-6:])[:1200]
    summary = analysis.get("transcript_summary") or ""
    ts = times_in(summary)
    if ts:
        return ts[-1], "summary", summary[:600]
    return FALLBACK_TIME, "fallback", ("\n".join(lines[-6:]) or summary)[:1200]


def build_email(s: dict, contacts: dict, appt: str, confirmed: bool) -> EmailMessage:
    name = s.get("student_name") or DEFAULT_STUDENT
    course = s.get("course_name") or DEFAULT_COURSE
    today = datetime.now().strftime("%Y-%m-%d")
    appt_en = appt if confirmed else f"{appt} (requested, to be confirmed)"
    appt_hu = appt.replace(" CET", "") + (" (CET)" if confirmed else " (CET, megerősítés alatt)")
    msg = EmailMessage()
    msg["Subject"] = f"Absence notice / Hiányzás bejelentése – {name} – {course} – {today}"
    msg["From"] = env("SMTP_EMAIL") or "Sera demo <sera-demo@localhost>"
    msg["To"] = contacts.get("lecturer_email")
    # Data minimisation: the lecturer gets the absence and the appointment, not the medical details.
    msg.set_content(f"""Dear Lecturer,

I am writing to inform you that I am ill today ({today}) and unfortunately cannot attend today's {course} class.
I have a medical appointment with the campus doctor today at {appt_en}.
I will provide a medical certificate if required and catch up on the material I miss.

Kind regards,
{name}

————————————————————————

Tisztelt Oktató!

Tájékoztatom, hogy ma ({today}) beteg vagyok, ezért sajnos nem tudok részt venni a mai {course} órán.
Ma {appt_hu} órakor időpontom van az egyetemi orvosnál.
Szükség esetén orvosi igazolást hozok, és a kimaradt anyagot pótolom.

Tisztelettel:
{name}

—
Sent with the student's permission by StudentMate Agent.
""")
    return msg


def email_configured() -> bool:
    return bool(env("SMTP_EMAIL") and env("SMTP_APP_PASSWORD"))


def send_email(msg: EmailMessage) -> None:
    user, password = env("SMTP_EMAIL"), env("SMTP_APP_PASSWORD").replace(" ", "")
    if not user or not password:
        raise RuntimeError("SMTP not configured: set SMTP_EMAIL and SMTP_APP_PASSWORD in backend/.env")
    host, port = env("SMTP_HOST", "smtp.gmail.com"), int(env("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


async def complete_mission(payload: dict, source_label: str) -> None:
    appt, source, excerpt = extract_appointment(payload)
    confirmed = source != "fallback"
    if source_label == "simulated" and confirmed:
        source, excerpt = "manual", None  # typed on the fallback screen, not heard in a call
    mission.update(f"Call finished ({source_label}). Appointment: {appt} [{source}].",
                   status="SENDING_EMAIL", appointment_time=appt, appointment_time_source=source,
                   transcript_excerpt=excerpt)
    snap = mission.snapshot()
    to = snap["contacts"].get("lecturer_email") or env("LECTURER_EMAIL") or None
    if not email_configured() and to:
        msg = build_email(snap["student"], {**snap["contacts"], "lecturer_email": to}, appt, confirmed)
        mission.update(f"Absence email prepared for {to} (demo mode: not actually sent).",
                       email={"status": "simulated", "to": to, "subject": msg["Subject"],
                              "body": msg.get_content(), "error": None})
    elif not email_configured():
        mission.update("Lecturer email is switched off (no SMTP settings): skipped.",
                       email={"status": "skipped", "error": None})
    elif not to:
        mission.update("No lecturer email given: email skipped.", email={"status": "skipped", "error": None})
    else:
        try:
            msg = build_email(snap["student"], snap["contacts"], appt, confirmed)
            await asyncio.to_thread(send_email, msg)
            mission.update(f"Email sent to {to}.", email={"status": "sent", "to": to,
                                                          "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                          "subject": msg["Subject"], "error": None})
        except Exception as e:  # never report a failed email as sent
            mission.update(f"Email FAILED: {type(e).__name__}: {str(e)[:200]}",
                           email={"status": "failed", "error": f"{type(e).__name__}: {str(e)[:200]}"})

    student_phone = snap["contacts"].get("student_phone")
    confirm_agent = env("ELEVENLABS_STUDENT_AGENT_ID")
    if student_phone and confirm_agent:
        try:
            r = await _place_call(student_phone, {"student_name": snap["student"].get("student_name", DEFAULT_STUDENT),
                                                  "appointment_time": appt}, confirm_agent)
            mission.update("Confirmation call to the student started.",
                           student_callback={"status": "calling", "conversation_id": r.get("conversation_id")})
        except HTTPException as e:
            mission.update(f"Student confirmation call failed: {e.detail}", student_callback={"status": "failed"})
    mission.update("Mission completed.", status="COMPLETED")


def verify_signature(raw: bytes, header: str | None) -> bool:
    """ElevenLabs-Signature: t=<unix>,v0=<hex hmac_sha256(secret, f"{t}.{body}")>. Skipped if no secret is set."""
    secret = env("ELEVENLABS_WEBHOOK_SECRET")
    if not secret:
        return True
    if not header:
        return False
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts, sig = parts.get("t", ""), parts.get("v0", "")
    if not ts.isdigit() or abs(time.time() - int(ts)) > 30 * 60:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@router.post("/elevenlabs-webhook")
async def elevenlabs_webhook(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("elevenlabs-signature")):
        mission.update("A webhook was REJECTED (invalid signature). Check ELEVENLABS_WEBHOOK_SECRET or use the fallback.")
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "Body must be JSON")
    etype = payload.get("type", "post_call_transcription")
    if etype != "post_call_transcription":
        return {"ok": True, "ignored": etype}  # e.g. post_call_audio
    snap = mission.snapshot()
    conv = (payload.get("data") or {}).get("conversation_id")
    if snap["status"] in ("COMPLETED", "SENDING_EMAIL"):
        return {"ok": True, "ignored": "mission already processed"}
    if snap["conversation_id"] and conv and conv != snap["conversation_id"]:
        return {"ok": True, "ignored": "different conversation"}
    if snap["status"] not in ("CALLING_DOCTOR", "CALL_FAILED"):
        return {"ok": True, "ignored": f"no active call (status {snap['status']})"}
    background.add_task(complete_mission, payload, "ElevenLabs webhook")
    return {"ok": True}


class SimulateRequest(BaseModel):
    appointment_time: Optional[str] = Field(None, description="e.g. '14:30' — if empty, the fallback 14:30 is used")
    lecturer_email: Optional[str] = None
    student_name: Optional[str] = None
    course_name: Optional[str] = None


@router.post("/simulate-call-complete")
async def simulate_call_complete(body: SimulateRequest):
    """Stage fallback: finish step 3 without a real call (e.g. no mobile signal in the venue)."""
    if body.lecturer_email:
        mission.update(contacts={"lecturer_email": body.lecturer_email}, email={"to": body.lecturer_email})
    if body.student_name or body.course_name:
        mission.update(student={k: v for k, v in {"student_name": body.student_name,
                                                  "course_name": body.course_name}.items() if v})
    msg = f"Az időpont rendben, ma {body.appointment_time} órakor várjuk." if body.appointment_time else ""
    payload = {"type": "post_call_transcription", "data": {"transcript": [{"role": "user", "message": msg}] if msg else []}}
    await complete_mission(payload, "simulated")
    return mission.snapshot()


@router.get("/mission-status")
def mission_status():
    return mission.snapshot()


@router.post("/mission-reset")
def mission_reset():
    mission.reset()
    return mission.snapshot()
