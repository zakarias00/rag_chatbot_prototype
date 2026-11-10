"""Simple lexical check that a retrieved chunk relates to the question.

Not a semantic entailment or fact-checking model.
"""
from __future__ import annotations

import re

from src.rag.querying import API_NAME, MODULE_HINT, evidence_facets

TOKEN = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", re.I)
STOP = set("a also an and are as at be by calculate can could describe difference do does explain for from how i in is it me my of on or please show tell that the their this to use what when where which why with work would you your python documentation docs doc about question using between information".split())

# Only static Python documentation is indexed: not private company or live data.
UNSUPPORTED = re.compile(
    r"\b(?:my|our)\s+(?:company|organisation|organization)(?:'s)?\b"
    r"|\b(?:current|latest|today's)\s+(?:price|pricing|rate\s+limit)\b"
    r"|\b(?:api\s+rate\s+limit|cloud\s+service\s+price)\b"
    r"|\b(?:my|our)\s+virtual\s+environment\b.*\b(?:currently|right\s+now)\b", re.I,
)


def matches_facet(facet: str, document: dict) -> bool:
    """Require some shared terms and any explicitly named API/module.

    This is a cheap lexical relevance check, not semantic fact verification.
    """
    text = " ".join(str(document.get(key, "")) for key in ("title", "section", "text"))
    text = re.sub(r"\\([_*])", r"\1", text)  # Undo Markdown escapes in docs.
    for name in API_NAME.findall(facet):
        if not re.search(rf"(?<![\w.]){re.escape(name)}(?![\w.])", text, re.I):
            return False
    module = MODULE_HINT.search(facet)
    if module and document.get("document_id", "").lower() != module[1].lower():
        return False

    terms = {term.lower() for term in TOKEN.findall(facet) if len(term) > 1 and term.lower() not in STOP}
    normalized = text.lower().replace("_", " ").replace(".", " ")
    matched = sum(
        bool(re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text, re.I))
        or ("." not in term and bool(re.search(rf"\b{re.escape(term)}\b", normalized)))
        for term in terms
    )
    return bool(terms) and matched >= (1 if len(terms) <= 2 else 2) and matched / len(terms) >= 0.40


def filter_evidence(question: str, documents: list[dict]) -> tuple[list[dict], int, int]:
    """Return relevant chunks, number of supported facets, and total facets."""
    facets = evidence_facets(question)
    if UNSUPPORTED.search(question):
        return [], 0, len(facets)
    relevant = [doc for doc in documents if any(matches_facet(facet, doc) for facet in facets)]
    covered = sum(any(matches_facet(facet, doc) for doc in relevant) for facet in facets)
    return relevant, covered, len(facets)


