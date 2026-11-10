"""Helpers for functional evaluation."""
from __future__ import annotations

import json
from pathlib import Path


def validate_labels(cases: list[dict], chunks: list[dict]) -> None:
    """Check the manually assigned gold labels before scoring anything."""
    sources = {chunk["chunk_id"]: chunk["document_id"] for chunk in chunks}
    for case in cases:
        cid = case["id"]
        points = case["expected_points"]
        requirements = case.get("required_evidence")
        if not isinstance(requirements, list):
            raise ValueError(f"{cid}: required_evidence must be a list")
        if "search_documentation" in case["expected_tools"] and case["category"] != "unsupported" and not requirements:
            raise ValueError(f"{cid}: expected documentation evidence is missing")
        if requirements and "search_documentation" not in case["expected_tools"]:
            raise ValueError(f"{cid}: evidence labels require a documentation search")

        labeled_points = set()
        labeled_chunks = set()
        for requirement in requirements:
            point = requirement["point"]
            chunk_ids = requirement["supporting_chunk_ids"]
            if point not in points or point in labeled_points:
                raise ValueError(f"{cid}: unknown or duplicated answer point: {point}")
            if not isinstance(chunk_ids, list) or not chunk_ids or len(chunk_ids) != len(set(chunk_ids)):
                raise ValueError(f"{cid}: each answer point needs unique supporting chunk IDs")
            unknown = set(chunk_ids) - sources.keys()
            if unknown:
                raise ValueError(f"{cid}: unknown supporting chunk IDs: {sorted(unknown)}")
            labeled_points.add(point)
            labeled_chunks.update(chunk_ids)

        if (len(case["relevant_chunk_ids"]) != len(set(case["relevant_chunk_ids"]))
                or set(case["relevant_chunk_ids"]) != labeled_chunks):
            raise ValueError(f"{cid}: relevant_chunk_ids disagrees with required_evidence")
        source_count = len({sources[chunk_id] for chunk_id in labeled_chunks})
        if case["category"] == "multi_source" and source_count < 2:
            raise ValueError(f"{cid}: multi_source case must need at least two sources")
        if case["category"] == "single_source" and source_count != 1:
            raise ValueError(f"{cid}: single_source case must need exactly one source")


def evidence_coverage(requirements: list[dict], chunk_ids: list[str]) -> float | None:
    """Fraction of answer points backed by at least one retrieved chunk."""
    if not requirements:
        return None  
    retrieved = set(chunk_ids)
    covered = sum(bool(retrieved.intersection(r["supporting_chunk_ids"])) for r in requirements)
    return covered / len(requirements)


def load_reviews(path: Path | None, cases: list[dict]) -> dict[str, dict]:
    """Optional human answer reviews: {"id":"q01","point_correct":[true,false]}."""
    if path is None:
        return {}
    case_by_id = {case["id"]: case for case in cases}
    reviews = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        review = json.loads(line)
        cid = review.get("id")
        if cid not in case_by_id or cid in reviews:
            raise ValueError(f"Unknown or duplicate review ID: {cid!r}")
        values = review.get("point_correct")
        if (not isinstance(values, list)
                or len(values) != len(case_by_id[cid]["expected_points"])
                or any(type(value) is not bool for value in values)):
            raise ValueError(f"{cid}: point_correct needs one boolean per expected answer point")
        reviews[cid] = review
    return reviews
