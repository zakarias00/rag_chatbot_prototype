from __future__ import annotations

from src.generation.base import GenerationResult


class DummyGenerator:
    """Return the selected excerpts verbatim with numbered source URLs."""

    def generate(self, question: str, documents: list[dict]) -> GenerationResult:
        parts = [
            f"[{number}] {doc.get('text', '')}\nSource: {doc.get('source_url', '')}"
            for number, doc in enumerate(documents, start=1)
        ]
        return GenerationResult("\n\n".join(parts), "dummy")
