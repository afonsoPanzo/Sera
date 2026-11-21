"""Text-to-speech with ElevenLabs: Sera reads its answers aloud (EN/HU).

The API key stays on the server. Config in backend/.env:
  ELEVENLABS_API_KEY   required
  ELEVENLABS_VOICE_ID  voice used for both languages (pick a multilingual voice in your ElevenLabs account)
  ELEVENLABS_MODEL     default eleven_multilingual_v2 (supports Hungarian)
"""

from __future__ import annotations

import os
import re

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MAX_CHARS = 1500  # keeps credits under control; longer replies are cut at a sentence end


class VoiceNotConfigured(RuntimeError):
    pass


class VoiceError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def config() -> dict:
    return {
        "api_key": os.getenv("ELEVENLABS_API_KEY", ""),
        "voice_id": os.getenv("ELEVENLABS_VOICE_ID", ""),
        "model": os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
    }


def clean_for_speech(text: str) -> str:
    """Remove markdown and links so the voice doesn't read symbols or URLs."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)          # [label](url) -> label
    t = re.sub(r"https?://\S+", "", t)                         # bare urls
    t = re.sub(r"[*_`#>|]+", "", t)                            # markdown symbols
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.MULTILINE)      # bullets
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    if len(t) > MAX_CHARS:
        cut = t[:MAX_CHARS]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("\n"))
        t = cut[: end + 1] if end > MAX_CHARS // 2 else cut
    return t


def synthesize(text: str, language: str) -> bytes:
    """Return MP3 bytes. Raises VoiceNotConfigured or VoiceError."""
    cfg = config()
    if not cfg["api_key"] or not cfg["voice_id"]:
        raise VoiceNotConfigured("ElevenLabs is not configured (ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID)")
    speech = clean_for_speech(text)
    if not speech:
        raise VoiceError(422, "Nothing to read")

    import httpx

    body = {"text": speech, "model_id": cfg["model"]}
    if language in ("en", "hu"):
        body["language_code"] = language
    try:
        r = httpx.post(API_URL.format(voice_id=cfg["voice_id"]),
                       params={"output_format": "mp3_44100_128"},
                       headers={"xi-api-key": cfg["api_key"], "Accept": "audio/mpeg"},
                       json=body, timeout=30)
    except httpx.HTTPError as e:
        raise VoiceError(502, f"Voice service unreachable: {type(e).__name__}")
    if r.status_code == 200 and r.content:
        return r.content
    detail = ""
    try:
        d = r.json().get("detail")
        detail = d.get("message") or d.get("status") if isinstance(d, dict) else str(d or "")
    except Exception:
        pass
    if r.status_code in (401, 403):
        raise VoiceError(503, f"Voice service rejected the API key or plan. {detail}".strip())
    if r.status_code == 429:
        raise VoiceError(503, "Voice service is busy or out of credits, please try again")
    raise VoiceError(502, f"Voice service error {r.status_code}. {detail}".strip())
