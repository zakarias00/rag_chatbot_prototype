from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GenerationResult:
    """Visible answer and the backend that produced it."""

    text: str
    backend: str
    fallback_reason: str | None = None


class AnswerGenerator(Protocol):
    def generate(self, question: str, documents: list[dict]) -> GenerationResult:
        """Answer using the supplied retrieved documents."""


class OllamaUnavailable(Exception):
    """Expected provider availability or response failure, safe for fallback."""


class FallbackGenerator:
    """Use a dummy generator only for expected Ollama failures."""

    def __init__(self, primary: AnswerGenerator, fallback: AnswerGenerator | None = None):
        if fallback is None:
            from .dummy import DummyGenerator
            fallback = DummyGenerator()
        self.primary = primary
        self.fallback = fallback

    def generate(self, question: str, documents: list[dict]) -> GenerationResult:
        try:
            return self.primary.generate(question, documents)
        except OllamaUnavailable as exc:
            result = self.fallback.generate(question, documents)
            return GenerationResult(result.text, result.backend, str(exc))
