from __future__ import annotations

from dataclasses import dataclass
import math
import os
from urllib.parse import urlsplit

from src.generation.dummy import DummyGenerator
from src.generation.base import FallbackGenerator
from src.generation.ollama import OllamaGenerator
from src.generation.base import AnswerGenerator


@dataclass(frozen=True)
class Settings:
    generator: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:1.7b"
    ollama_timeout_seconds: float = 35.0


def load_settings() -> Settings:
    """Read and validate non-secret settings from environment variables."""
    generator = os.getenv("RAG_GENERATOR", "ollama").strip().lower()
    if generator not in {"ollama", "dummy"}:
        raise ValueError("RAG_GENERATOR must be 'ollama' or 'dummy'")
    
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    parsed = urlsplit(base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
        raise ValueError("OLLAMA_BASE_URL must be an HTTP(S) base URL without credentials, query, or fragment")

    model = os.getenv("OLLAMA_MODEL", "qwen3:1.7b").strip()
    
    if not model:
        raise ValueError("OLLAMA_MODEL must not be empty")
    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "35"))
    except ValueError as exc:
        raise ValueError("OLLAMA_TIMEOUT_SECONDS must be a positive number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("OLLAMA_TIMEOUT_SECONDS must be a positive finite number")

    return Settings(generator, base_url, model, timeout)


def create_generator(settings: Settings | None = None) -> AnswerGenerator:
    """Create the configured backend; Ollama failures fall back to the dummy."""
    settings = settings or load_settings()
    if settings.generator == "dummy":
        return DummyGenerator()
    return FallbackGenerator(OllamaGenerator(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout_seconds,
    ))
