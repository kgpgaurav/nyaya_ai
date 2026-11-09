from .config import Settings
from .db import EMBED_DIM

DEFAULTS = {
    "openai": "text-embedding-3-small",
    "gemini": "gemini-embedding-001",
    "ollama": "nomic-embed-text",
}


def build_embedder(settings: Settings):
    provider = settings.embedding_provider
    if provider in ("", "none"):
        return None
    model = settings.embedding_model or DEFAULTS.get(provider, "")
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model, dimensions=EMBED_DIM, api_key=settings.openai_api_key)
    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=model, google_api_key=settings.google_api_key, output_dimensionality=EMBED_DIM
        )
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=model, base_url=settings.ollama_base_url)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER {provider!r}")
