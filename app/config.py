from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://nyaya:nyaya@localhost:5432/nyaya"

    llm_provider: str = "openai"
    llm_model: str = ""
    llm_temperature: float = 0.1
    llm_timeout: float = 45
    groq_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    mock_fixtures: str = "tests/mock_llm.json"

    embedding_provider: str = "none"
    embedding_model: str = ""

    stt_provider: str = "openai"
    stt_model: str = "whisper-1"
    sarvam_api_key: str = ""

    cookie_secure: bool = False
    session_ttl_hours: int = 72
    max_calls_per_case: int = 60
    max_calls_per_day: int = 1500
    max_message_chars: int = 4000
    max_audio_bytes: int = 8_000_000

    @field_validator("database_url")
    @classmethod
    def _driver(cls, v: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def psycopg_url(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @property
    def resolved_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return {
            "groq": "llama-3.3-70b-versatile",
            "openai": "gpt-4.1-mini",
            "gemini": "gemini-2.5-flash",
            "ollama": "qwen2.5:7b-instruct",
            "mock": "scripted",
        }.get(self.llm_provider, "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
