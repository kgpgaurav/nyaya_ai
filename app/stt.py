import hashlib
import json
from pathlib import Path

import httpx

from .config import Settings


class STTError(RuntimeError):
    pass


class GroqWhisper:
    url = "https://api.groq.com/openai/v1/audio/transcriptions"

    def __init__(self, settings: Settings):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set")
        self.key, self.model = settings.groq_api_key, settings.stt_model

    async def transcribe(self, audio: bytes, filename: str, language: str | None) -> str:
        data = {"model": self.model, "response_format": "json", "temperature": "0"}
        if language in ("en", "hi"):
            data["language"] = language
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                self.url, headers={"Authorization": f"Bearer {self.key}"}, data=data, files={"file": (filename, audio)}
            )
        if r.status_code != 200:
            raise STTError(f"transcription failed with status {r.status_code}")
        return r.json().get("text", "").strip()



class OpenAIWhisper:
    """Use the same OPENAI_API_KEY for Whisper and chat."""

    url = "https://api.openai.com/v1/audio/transcriptions"

    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self.key = settings.openai_api_key
        self.model = settings.stt_model if settings.stt_model not in ("", "whisper-large-v3-turbo") else "whisper-1"

    async def transcribe(self, audio: bytes, filename: str, language: str | None) -> str:
        data = {"model": self.model, "response_format": "json"}
        if language in ("en", "hi"):
            data["language"] = language
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.key}"},
                data=data,
                files={"file": (filename, audio)},
            )
        if r.status_code != 200:
            raise STTError(f"transcription failed with status {r.status_code}")
        return r.json().get("text", "").strip()


class SarvamSTT:
    url = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, settings: Settings):
        if not settings.sarvam_api_key:
            raise ValueError("SARVAM_API_KEY is not set")
        self.key = settings.sarvam_api_key
        self.model = settings.stt_model if settings.stt_model.startswith("saar") else "saaras:v3"

    async def transcribe(self, audio: bytes, filename: str, language: str | None) -> str:
        data = {"model": self.model, "language_code": {"hi": "hi-IN", "en": "en-IN"}.get(language or "", "unknown")}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                self.url, headers={"api-subscription-key": self.key}, data=data, files={"file": (filename, audio)}
            )
        if r.status_code != 200:
            raise STTError(f"transcription failed with status {r.status_code}")
        return r.json().get("transcript", "").strip()


class MockSTT:
    def __init__(self, path: str):
        p = Path(path)
        self.table = json.loads(p.read_text(encoding="utf-8")).get("stt", {}) if p.exists() else {}

    async def transcribe(self, audio: bytes, filename: str, language: str | None) -> str:
        digest = hashlib.sha256(audio).hexdigest()
        if digest not in self.table:
            raise STTError("no scripted transcript for this audio")
        return self.table[digest]


def build_stt(settings: Settings):
    if settings.stt_provider == "mock" or settings.llm_provider == "mock":
        return MockSTT(settings.mock_fixtures)
    if settings.stt_provider == "openai":
        return OpenAIWhisper(settings)
    if settings.stt_provider == "sarvam":
        return SarvamSTT(settings)
    if settings.stt_provider == "groq":
        return GroqWhisper(settings)
    if settings.stt_provider in ("", "none"):
        return None
    raise ValueError(f"Unknown STT_PROVIDER {settings.stt_provider!r}")
