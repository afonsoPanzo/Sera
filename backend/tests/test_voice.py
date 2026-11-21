import httpx

from app import voice


class FakeResp:
    def __init__(self, status, content=b"", js=None):
        self.status_code, self.content, self._js = status, content, js

    def json(self):
        return self._js or {}


def configure(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice123")


def test_not_configured(client, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    r = client.post("/api/speak", json={"text": "Hello"})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_speak_returns_mp3_and_sends_clean_text(client, monkeypatch):
    configure(monkeypatch)
    seen = {}

    def fake_post(url, params, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return FakeResp(200, b"ID3fake-mp3")

    monkeypatch.setattr(httpx, "post", fake_post)
    r = client.post("/api/speak", json={"text": "**Hi!** See [NEAK](https://neak.gov.hu) now.", "language": "hu"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake-mp3"
    assert seen["url"].endswith("/voice123")
    assert seen["headers"]["xi-api-key"] == "test-key"
    assert seen["json"]["text"] == "Hi! See NEAK now."
    assert seen["json"]["language_code"] == "hu"


def test_bad_key_and_rate_limit(client, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(401, js={"detail": {"message": "invalid key"}}))
    r = client.post("/api/speak", json={"text": "Hello"})
    assert r.status_code == 503 and "invalid key" in r.json()["detail"]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(429))
    assert client.post("/api/speak", json={"text": "Hello"}).status_code == 503


def test_validation(client):
    assert client.post("/api/speak", json={"text": ""}).status_code == 422
    assert client.post("/api/speak", json={"text": "hi", "language": "pt"}).status_code == 422


def test_clean_for_speech_cuts_long_text():
    t = voice.clean_for_speech(("This is a sentence. " * 200))
    assert len(t) <= voice.MAX_CHARS and t.endswith(".")
    assert voice.clean_for_speech("Where to check: https://oif.gov.hu") == "Where to check:"
