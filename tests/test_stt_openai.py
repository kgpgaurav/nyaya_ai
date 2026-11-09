"""The speech endpoint can use the chat provider's OpenAI key alone."""
import asyncio

import httpx
import pytest

from app.config import Settings
from app.stt import OpenAIWhisper, STTError, build_stt


def test_openai_stt_uses_openai_key(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"text": "नमस्ते"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))
    settings = Settings(
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
        openai_api_key="test-only-key",
        stt_provider="openai",
        stt_model="whisper-1",
    )
    instance = build_stt(settings)
    assert isinstance(instance, OpenAIWhisper)
    assert asyncio.run(instance.transcribe(b"wav-bytes", "voice.wav", "hi")) == "नमस्ते"
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/audio/transcriptions"
    assert requests[0].headers["authorization"] == "Bearer test-only-key"
    assert b'name="model"' in requests[0].content
    assert b"whisper-1" in requests[0].content
    assert b'hi' in requests[0].content


def test_openai_stt_missing_key():
    settings = Settings(stt_provider="openai", openai_api_key="")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_stt(settings)


def test_openai_stt_provider_error(monkeypatch):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "bad key"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))
    settings = Settings(stt_provider="openai", openai_api_key="test-only-key")
    with pytest.raises(STTError, match="401"):
        asyncio.run(OpenAIWhisper(settings).transcribe(b"wav-bytes", "voice.wav", None))
