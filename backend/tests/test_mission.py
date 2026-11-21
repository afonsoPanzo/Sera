import hashlib
import hmac
import json
import time

import httpx
import pytest

from app import mission as m

STAGE_MSG = "I woke up sick with a high fever, I'm allergic to penicillin, and I can't attend my class today."


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    m.mission.reset()
    for k in ("ELEVENLABS_WEBHOOK_SECRET", "ELEVENLABS_STUDENT_AGENT_ID", "LECTURER_EMAIL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent_test")
    monkeypatch.setenv("ELEVENLABS_AGENT_PHONE_NUMBER_ID", "phnum_test")
    monkeypatch.setenv("SMTP_EMAIL", "sender@example.org")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "abcd efgh ijkl mnop")
    yield


class FakeAsyncClient:
    calls = []
    response = (200, {"success": True, "message": "ok", "conversation_id": "conv_123", "callSid": "CA1"})

    def __init__(self, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers, json):
        FakeAsyncClient.calls.append({"url": url, "headers": headers, "json": json})
        status, body = FakeAsyncClient.response
        return httpx.Response(status, json=body)


@pytest.fixture
def fake_call(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = (200, {"success": True, "conversation_id": "conv_123", "callSid": "CA1"})
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(m, "send_email", lambda msg: out.append(msg))
    return out


def confirm_body(**kw):
    b = {"doctor_phone": "+36 30 123 4567", "lecturer_email": "lecturer@example.org", "student_name": "Alex Vance",
         "symptoms": "magas láz", "allergies": "penicillin", "preferred_window": "Ma 15:00 előtt"}
    b.update(kw)
    return b


def test_triage_stage_sentence(client):
    r = client.post("/api/chat-triage", json={"message": STAGE_MSG}).json()
    assert r["student_name"] == "Alex Vance" and r["course_name"] == "Algorithms & Data Structures"
    assert r["symptoms"] == "high fever" and r["symptoms_hu"] == "magas láz"
    assert r["allergies"] == "penicillin" and r["misses_class"] is True
    assert "penicillin allergy" in r["confirmation_question"] and "in Hungarian" in r["confirmation_question"]
    assert client.get("/api/mission-status").json()["status"] == "TRIAGE_DONE"


def test_triage_emergency_does_not_offer_booking(client):
    r = client.post("/api/chat-triage", json={"message": "I have chest pain and can't breathe"}).json()
    assert r["emergency"] is True and r["needs_confirmation"] is False and "112" in r["confirmation_question"]


def test_confirm_places_exact_elevenlabs_call(client, fake_call):
    r = client.post("/api/confirm-and-execute", json=confirm_body())
    assert r.status_code == 200, r.text
    call = fake_call.calls[0]
    assert call["url"] == "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"
    assert call["headers"] == {"xi-api-key": "test-key"}
    assert call["json"] == {
        "agent_id": "agent_test", "agent_phone_number_id": "phnum_test", "to_number": "+36301234567",
        "conversation_initiation_client_data": {"dynamic_variables": {
            "student_name": "Alex Vance", "symptoms": "magas láz", "allergies": "penicillin",
            "preferred_window": "Ma 15:00 előtt"}}}
    s = client.get("/api/mission-status").json()
    assert s["status"] == "CALLING_DOCTOR" and s["conversation_id"] == "conv_123"


def test_confirm_validates_phone_and_config(client, fake_call, monkeypatch):
    assert client.post("/api/confirm-and-execute", json=confirm_body(doctor_phone="0630123")).status_code == 422
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    r = client.post("/api/confirm-and-execute", json=confirm_body())
    assert r.status_code == 503
    assert client.get("/api/mission-status").json()["status"] == "CALL_FAILED"


def test_call_rejected_is_not_reported_as_calling(client, fake_call):
    fake_call.response = (422, {"detail": {"message": "invalid number"}})
    r = client.post("/api/confirm-and-execute", json=confirm_body())
    assert r.status_code == 502 and "invalid number" in r.json()["detail"]
    assert client.get("/api/mission-status").json()["status"] == "CALL_FAILED"


def webhook_payload(text, conv="conv_123"):
    return {"type": "post_call_transcription", "event_timestamp": int(time.time()),
            "data": {"conversation_id": conv, "transcript": [
                {"role": "agent", "message": "Jó napot, Alex Vance nevében hívom, magas láza van."},
                {"role": "user", "message": text}]}}


def test_webhook_completes_mission_and_sends_email(client, fake_call, sent):
    client.post("/api/confirm-and-execute", json=confirm_body())
    r = client.post("/api/elevenlabs-webhook", json=webhook_payload("Rendben, fél három jó lesz, várjuk."))
    assert r.status_code == 200
    s = client.get("/api/mission-status").json()
    assert s["status"] == "COMPLETED" and s["appointment_time"] == "14:30 CET"
    assert s["appointment_time_source"] == "transcript" and s["email"]["status"] == "sent"
    body = sent[0].get_content()
    assert sent[0]["To"] == "lecturer@example.org"
    assert "cannot attend today's Algorithms & Data Structures class" in body and "Tisztelt Oktató" in body
    assert "penicillin" not in body.lower()  # medical details are not shared with the lecturer
    assert "to be confirmed" not in body


def test_webhook_ignores_audio_other_conversations_and_duplicates(client, fake_call, sent):
    client.post("/api/confirm-and-execute", json=confirm_body())
    assert client.post("/api/elevenlabs-webhook", json={"type": "post_call_audio", "data": {}}).json()["ignored"]
    assert client.post("/api/elevenlabs-webhook", json=webhook_payload("15:00", conv="other")).json()["ignored"]
    client.post("/api/elevenlabs-webhook", json=webhook_payload("Ma 13:45-kor tud jönni."))
    client.post("/api/elevenlabs-webhook", json=webhook_payload("Ma 13:45-kor tud jönni."))
    assert len(sent) == 1 and client.get("/api/mission-status").json()["appointment_time"] == "13:45 CET"


def test_webhook_signature(client, fake_call, sent, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", "whsec_test")
    client.post("/api/confirm-and-execute", json=confirm_body())
    raw = json.dumps(webhook_payload("14:00")).encode()
    assert client.post("/api/elevenlabs-webhook", content=raw).status_code == 401
    ts = str(int(time.time()))
    sig = hmac.new(b"whsec_test", f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    r = client.post("/api/elevenlabs-webhook", content=raw, headers={"ElevenLabs-Signature": f"t={ts},v0={sig}"})
    assert r.status_code == 200 and client.get("/api/mission-status").json()["status"] == "COMPLETED"


def test_fallback_time_is_flagged(client, fake_call, sent):
    client.post("/api/confirm-and-execute", json=confirm_body())
    client.post("/api/elevenlabs-webhook", json=webhook_payload("Rendben, viszonthallásra."))
    s = client.get("/api/mission-status").json()
    assert s["appointment_time"] == "14:30 CET" and s["appointment_time_source"] == "fallback"
    assert "to be confirmed" in sent[0].get_content()


def test_email_failure_is_reported(client, fake_call, monkeypatch):
    def boom(msg):
        raise OSError("SMTP down")

    monkeypatch.setattr(m, "send_email", boom)
    client.post("/api/confirm-and-execute", json=confirm_body())
    client.post("/api/elevenlabs-webhook", json=webhook_payload("15:00"))
    s = client.get("/api/mission-status").json()
    assert s["email"]["status"] == "failed" and "SMTP down" in s["email"]["error"]


def test_simulate_without_call(client, sent):
    r = client.post("/api/simulate-call-complete", json={"appointment_time": "14:30", "lecturer_email": "lec@example.org"})
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "COMPLETED" and s["appointment_time"] == "14:30 CET" and s["email"]["status"] == "sent"
    assert s["appointment_time_source"] == "manual"
    assert client.post("/api/mission-reset").json()["status"] == "IDLE"


def test_email_switched_off_still_completes(client, fake_call, sent, monkeypatch):
    monkeypatch.delenv("SMTP_EMAIL")
    body = confirm_body()
    body.pop("lecturer_email")
    assert client.post("/api/confirm-and-execute", json=body).status_code == 200
    client.post("/api/elevenlabs-webhook", json=webhook_payload("Ma 15:00-kor várjuk."))
    s = client.get("/api/mission-status").json()
    assert s["status"] == "COMPLETED" and s["appointment_time"] == "15:00 CET"
    assert s["email"]["status"] == "skipped" and not sent
    r = client.post("/api/simulate-call-complete", json={"appointment_time": "16:00"})
    assert r.status_code == 200


@pytest.mark.parametrize("text,expected", [
    ("Délután 3 órakor tud jönni.", ["15:00 CET"]),
    ("fél kettőre jöjjön", ["13:30 CET"]),
    ("Ma 14.15-kor", ["14:15 CET"]),
    ("Can she come at 2 pm?", ["14:00 CET"]),
    ("A díj 3500 Ft, kód 106-2-12345", []),
])
def test_times_in(text, expected):
    assert m.times_in(text) == expected


def test_simulated_email_to_default_lecturer(client, fake_call, sent, monkeypatch):
    monkeypatch.delenv("SMTP_EMAIL")
    monkeypatch.setenv("LECTURER_EMAIL", "lecturer.default@example.org")
    q = client.post("/api/chat-triage", json={"message": STAGE_MSG}).json()["confirmation_question"]
    assert "notify your lecturer" in q
    body = confirm_body()
    body.pop("lecturer_email")
    client.post("/api/confirm-and-execute", json=body)
    client.post("/api/elevenlabs-webhook", json=webhook_payload("Rendben, fél három."))
    s = client.get("/api/mission-status").json()
    assert s["status"] == "COMPLETED" and not sent
    assert s["email"]["status"] == "simulated" and s["email"]["to"] == "lecturer.default@example.org"
    assert "Tisztelt Oktató" in s["email"]["body"] and "14:30" in s["email"]["body"]


class FakeGet:
    """httpx.AsyncClient with both post (outbound call) and get (conversation status)."""
    conv = {}

    def __init__(self, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers, json):
        return httpx.Response(200, json={"success": True, "conversation_id": "conv_poll", "callSid": "CA9"})

    async def get(self, url, headers):
        return httpx.Response(200, json=FakeGet.conv)


def start_polled_call(client, monkeypatch, conv):
    FakeGet.conv = conv
    monkeypatch.setattr(httpx, "AsyncClient", FakeGet)
    assert client.post("/api/confirm-and-execute", json=confirm_body()).status_code == 200
    m.mission._last_poll = 0


def test_data_collection_matched_by_name():
    payload = {"data": {"analysis": {"data_collection_results": {
        "aitem_9401": {"data_collection_id": "aitem_9401", "name": "appointment_time", "value": "14:45"}}}}}
    assert m.extract_appointment(payload)[:2] == ("14:45 CET", "data_collection")


def test_poll_busy_marks_call_failed(client, monkeypatch, sent):
    start_polled_call(client, monkeypatch, {"status": "initiated", "metadata": {"phone_call": {"call_result": "busy"}}})
    s = client.get("/api/mission-status").json()
    assert s["status"] == "CALL_FAILED" and "busy" in s["events"][-1]["message"]


def test_poll_done_completes_without_webhook(client, monkeypatch, sent):
    start_polled_call(client, monkeypatch, {"status": "done", "metadata": {"phone_call": {"call_result": "answered"}},
                                            "transcript": [{"role": "user", "message": "Rendben, fél három."}],
                                            "analysis": {"data_collection_results": {}}})
    s = client.get("/api/mission-status").json()
    assert s["status"] == "COMPLETED" and s["appointment_time"] == "14:30 CET"
    # a late webhook for the same call must not complete it twice
    r = client.post("/api/elevenlabs-webhook", json=webhook_payload("15:00", conv="conv_poll")).json()
    assert r.get("ignored") and client.get("/api/mission-status").json()["appointment_time"] == "14:30 CET"


def test_poll_in_progress_keeps_calling(client, monkeypatch, sent):
    start_polled_call(client, monkeypatch, {"status": "in-progress", "metadata": {"phone_call": {"call_result": "answered"}}})
    s = client.get("/api/mission-status").json()
    assert s["status"] == "CALLING_DOCTOR" and s["call"]["status"] == "in-progress"


def test_webhook_without_screen_call_is_logged(client, sent):
    r = client.post("/api/elevenlabs-webhook", json=webhook_payload("15:00", conv="conv_other")).json()
    assert r["ignored"].startswith("no active call")
    assert "no call was started from this screen" in client.get("/api/mission-status").json()["events"][-1]["message"]
