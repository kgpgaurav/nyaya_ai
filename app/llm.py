import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)

PROVIDER_KEYS = {
    "groq": ("groq", "groq_api_key"),
    "openai": ("openai", "openai_api_key"),
    "gemini": ("google_genai", "google_api_key"),
    "ollama": ("ollama", None),
}


class LLMError(RuntimeError):
    pass


class MockMiss(LLMError):
    pass


@dataclass
class CallRecord:
    node: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    ok: bool = True
    error: str = ""


@dataclass
class Recorder:
    calls: list[CallRecord] = field(default_factory=list)


class LLM(Protocol):
    provider: str
    model: str

    async def structured(self, node: str, schema: type[T], system: str, user: str, recorder: Recorder, key: str) -> T: ...


class LangChainLLM:
    def __init__(self, settings: Settings):
        from langchain.chat_models import init_chat_model

        if settings.llm_provider not in PROVIDER_KEYS:
            raise ValueError(f"Unknown LLM_PROVIDER {settings.llm_provider!r}")
        lc_provider, key_attr = PROVIDER_KEYS[settings.llm_provider]
        kwargs = {"temperature": settings.llm_temperature, "timeout": settings.llm_timeout, "max_retries": 1}
        if key_attr:
            api_key = getattr(settings, key_attr)
            if not api_key:
                raise ValueError(f"{key_attr.upper()} is not set")
            kwargs["api_key"] = api_key
        if settings.llm_provider == "ollama":
            kwargs = {"temperature": settings.llm_temperature, "base_url": settings.ollama_base_url}
        self.provider = settings.llm_provider
        self.model = settings.resolved_model
        self._chat = init_chat_model(self.model, model_provider=lc_provider, **kwargs)
        self._method = "json_schema" if settings.llm_provider in ("ollama", "openai") else "function_calling"

    async def structured(self, node, schema, system, user, recorder, key=""):
        runnable = self._chat.with_structured_output(schema, method=self._method, include_raw=True)
        record = CallRecord(node=node, provider=self.provider, model=self.model)
        start = time.perf_counter()
        try:
            result = await runnable.ainvoke([("system", system), ("human", user)])
        except Exception as exc:
            record.ok, record.error = False, type(exc).__name__
            record.latency_ms = int((time.perf_counter() - start) * 1000)
            recorder.calls.append(record)
            raise LLMError(f"{node} call failed") from exc
        record.latency_ms = int((time.perf_counter() - start) * 1000)
        usage = getattr(result.get("raw"), "usage_metadata", None) or {}
        record.input_tokens = usage.get("input_tokens", 0)
        record.output_tokens = usage.get("output_tokens", 0)
        parsed = result.get("parsed")
        if parsed is None:
            record.ok, record.error = False, "parse_error"
            recorder.calls.append(record)
            raise LLMError(f"{node} returned unparseable output")
        recorder.calls.append(record)
        return parsed


class MockLLM:
    provider = "mock"
    model = "scripted"

    def __init__(self, fixtures: dict):
        self.fixtures = fixtures

    @classmethod
    def from_file(cls, path: str | Path) -> "MockLLM":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    async def structured(self, node, schema, system, user, recorder, key=""):
        recorder.calls.append(CallRecord(node=node, provider=self.provider, model=self.model))
        by_node = self.fixtures.get(node, {})
        if key not in by_node:
            raise MockMiss(f"No scripted {node} response for: {key[:80]!r}")
        return schema.model_validate(by_node[key])


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "mock":
        return MockLLM.from_file(settings.mock_fixtures)
    return LangChainLLM(settings)
