"""Small, deterministic multi-query retriever for the Python documentation."""
from __future__ import annotations

import re
from typing import Any

# Preserve dotted Python names such as json.dumps and Path.read_text.
API_NAME = re.compile(r"(?<![\w.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(?![\w.])")
CLAUSE_BREAK = re.compile(
    r"\s+and\s+(?=(?:parse|log|activate|read|write|create|handle|explain|"
    r"call|show|return|what|how|when|where|why|can|does|do)\b)", re.I,
)
MODULE_HINT = re.compile(r"\b(?:with|using|via)\s+(pathlib|json|venv|csv|logging)\b(?!\.)", re.I)


def split_needs(question: str) -> list[str]:
    """Split questions that ask for two independently answerable actions."""
    return [part.strip(" ,?.") for part in CLAUSE_BREAK.split(question)]


def evidence_facets(question: str) -> list[str]:
    """Return the parts for which the answer needs supporting documents."""
    clauses = split_needs(question)
    if len(clauses) > 1:
        return clauses
    names = list(dict.fromkeys(API_NAME.findall(question)))
    return names if len(names) > 1 else [question]


def search_facets(question: str) -> list[str]:
    """Search the full question plus smaller queries for multi-part questions."""
    question = " ".join(question.split())
    if not question:
        return []

    clauses = split_needs(question)
    names = list(dict.fromkeys(API_NAME.findall(question)))
    queries = [question]
    if len(clauses) > 1:
        queries.extend(part for part in clauses if len(part.split()) > 1)
    if len(clauses) > 1 or len(names) > 1:
        queries.extend(names)
    if re.search(r"\bcreate\b", question, re.I) and re.search(r"\bvenv|virtual environment\b", question, re.I):
        queries.append("venv creating virtual environments")

    return list(dict.fromkeys(queries))[:7]


def ranking_bonus(document: dict, query: str) -> float:
    """Give a modest preference to API definitions and the named module."""
    text = document.get("text", "")
    bonus = 0.0
    for name in set(API_NAME.findall(query)):
        if re.search(rf"(?m)^\s*`?{re.escape(name)}\s*\(", text):
            bonus += 0.25
        elif re.search(rf"(?<![\w.]){re.escape(name)}\s*\(", text):
            bonus += 0.04

    module = MODULE_HINT.search(query)
    if module and document.get("document_id", "").lower() == module[1].lower():
        bonus += 0.35
    if re.search(r"\bcreate\b", query, re.I) and re.search(r"\bcreat(?:e|es|ing|ion)\b", document.get("section", ""), re.I):
        bonus += 0.12
    return min(bonus, 0.65)


def retrieve_diversified(index: Any, question: str, *, k: int = 5, pool: int = 15) -> list[dict]:
    """Search several queries and return up to k unique, diverse chunks.

    `score` is the original TF-IDF similarity. `ranking_score` is only used
    to choose which chunks to show; it is not a confidence probability.
    """
    if not question.strip():
        raise ValueError("Question must not be empty")
    if k < 1 or pool < k:
        raise ValueError("k must be positive and pool must be >= k")

    found: dict[str, dict] = {}
    per_query: list[list[tuple[str, float]]] = []
    for query_number, query in enumerate(search_facets(question)):
        ranked = []
        for position, hit in enumerate(index.search(query, k=pool), start=1):
            chunk_id = hit["chunk_id"]
            rank = hit["score"] + ranking_bonus(hit, query) + 0.02 / position
            ranked.append((chunk_id, rank))

            if chunk_id not in found:
                found[chunk_id] = {**hit, "search_facets": [], "ranking_score": 0.0}
            result = found[chunk_id]
            result["score"] = max(result["score"], hit["score"])
            result["ranking_score"] = max(result["ranking_score"], rank)
            result["search_facets"].append(query_number)
        per_query.append(ranked)

    selected: list[str] = []
    # Reserve one result per additional query before filling by global rank.
    for candidates in per_query[1:]:
        available = [(chunk_id, rank) for chunk_id, rank in candidates if chunk_id not in selected]
        if available and len(selected) < k:
            selected.append(max(available, key=lambda item: item[1])[0])

    remaining = sorted(found, key=lambda cid: (-found[cid]["ranking_score"], -found[cid]["score"], cid))
    for chunk_id in remaining:
        if len(selected) == k:
            break
        if chunk_id not in selected:
            selected.append(chunk_id)
    return [found[chunk_id] for chunk_id in selected]
