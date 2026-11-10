from __future__ import annotations

import re

from src.generation.base import GenerationResult

_TOKEN = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", re.I)
_STOP = frozenset("a an and are as at be by can do does for from how i in is it of on or the to what when where which with you your".split())
_SYMBOL = re.compile(r"(?<![\w.])[A-Za-z_]\w*\.[A-Za-z_]\w*(?![\w.])")


def extract_excerpt(question: str, text: str, *, limit: int = 900) -> str:
    """Short, deterministic supporting excerpts. Not semantic generation or QA."""
    if len(text) <= limit:
        return text
    terms = {word.lower() for word in _TOKEN.findall(question) if word.lower() not in _STOP}
    symbols = set(_SYMBOL.findall(question))
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]

    def relevance(paragraph: str) -> float:
        lower = paragraph.lower()
        score = sum(1 for term in terms if term in lower)
        score += 5 * sum(bool(re.search(rf"(?<![\w.]){re.escape(sym)}(?![\w.])", paragraph)) for sym in symbols)
        if symbols and any(re.search(rf"(?m)^\s*`?{re.escape(sym)}\s*\(", paragraph)
                           for sym in symbols):
            score += 4
        if re.search(r"\bpython\s+-m\s+venv\b", paragraph) and "venv" in terms:
            score += 6
        if "read" in terms and re.search(r"\bread[_\s]?text\b", paragraph, re.I):
            score += 6
        return score

    ranked = sorted(enumerate(paragraphs), key=lambda pair: (-relevance(pair[1]), pair[0]))
    selected = []
    used = 0
    for index, paragraph in ranked:
        if len(selected) == 3:
            break
        # Retain a complete short paragraph when possible.
        available = min(limit - used, 400)
        segment = paragraph if len(paragraph) <= available else paragraph[:max(0, available)].rsplit(" ", 1)[0].rstrip()
        if not segment:
            break
        selected.append((index, segment))
        used += len(segment) + 2
        if used >= limit:
            break
    return "\n\n".join(part for _, part in sorted(selected))


class DummyGenerator:
    """Deterministic evidence excerpts, not a claim of LLM-style synthesis."""

    def generate(self, question: str, documents: list[dict]) -> GenerationResult:
        parts = [
            f"[{number}] {extract_excerpt(question, doc.get('text', ''))}\n"
            f"Source: {doc.get('source_url', '')}"
            for number, doc in enumerate(documents, start=1)
        ]
        return GenerationResult("\n\n".join(parts), "dummy")
