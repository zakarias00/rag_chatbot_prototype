from __future__ import annotations

import json
from pathlib import Path


def validate_required_evidence(cases: list[dict], chunks: list[dict]) -> None:
    """Fail fast on bad gold annotations before running the workflow."""
    source_by_id = {chunk["chunk_id"]: chunk["document_id"] for chunk in chunks}
    for case in cases:
        cid = case["id"]
        requirements = case.get("required_evidence")
        if not isinstance(requirements, list):
            raise ValueError(f"{cid}: required_evidence must be a list")
        if (not requirements and "search_documentation" in case["expected_tools"]
                and case["category"] != "unsupported"):
            raise ValueError(f"{cid}: documentation case must define required evidence")
        if requirements and "search_documentation" not in case["expected_tools"]:
            raise ValueError(f"{cid}: evidence labels but no documentation search expected")

        points_seen = set()
        union_ids = set()
        for requirement in requirements:
            if not isinstance(requirement, dict):
                raise ValueError(f"{cid}: every requirement must be an object")
            point = requirement.get("point")
            refs = requirement.get("supporting_chunk_ids")
            if not isinstance(point, str) or not point.strip() or point not in case["expected_points"]:
                raise ValueError(f"{cid}: point must match an expected_points entry: {point!r}")
            if point in points_seen:
                raise ValueError(f"{cid}: duplicate evidence point: {point}")
            points_seen.add(point)
            if not isinstance(refs, list) or not refs or any(not isinstance(x, str) for x in refs):
                raise ValueError(f"{cid}: supporting_chunk_ids must be a nonempty string list")
            if len(refs) != len(set(refs)):
                raise ValueError(f"{cid}: duplicate supporting chunk in {point!r}")
            unknown = sorted(set(refs) - source_by_id.keys())
            if unknown:
                raise ValueError(f"{cid}: unknown supporting chunk IDs: {unknown}")
            union_ids.update(refs)

        # The older chunk-label metrics are retained for comparability, but their
        # labels must come from the independently annotated evidence requirements.
        if set(case.get("relevant_chunk_ids", [])) != union_ids:
            raise ValueError(
                f"{cid}: relevant_chunk_ids must equal union of supporting_chunk_ids; "
                "do not use retrieved results to construct these labels"
            )
        docs = {source_by_id[ref] for ref in union_ids}
        if case["category"] == "multi_source" and len(docs) < 2:
            raise ValueError(f"{cid}: multi_source must require at least two distinct documents")
        if case["category"] == "single_source" and len(docs) != 1:
            raise ValueError(f"{cid}: single_source must require exactly one source document")


def score_evidence_points(requirements: list[dict], retrieved_ids: list[str]) -> dict:
    """Measure fraction of answer requirements with at least one supporting chunk.

    Empty requirements are out of scope for evidence retrieval and score None.
    """
    if not requirements:
        return {"point_coverage": None, "all_points_covered": None, "covered_points": []}
    seen = set(retrieved_ids)
    covered = [req["point"] for req in requirements
               if seen.intersection(req["supporting_chunk_ids"])]
    return {
        "point_coverage": len(covered) / len(requirements),
        "all_points_covered": len(covered) == len(requirements),
        "covered_points": covered,
    }


def summarize_point_metrics(records: list[dict]) -> dict:
    eligible = [r for r in records if r["retrieved_point_coverage_at_5"] is not None]
    multi = [r for r in eligible if r["category"] == "multi_source"]

    def aggregate(items: list[dict], prefix: str) -> dict:
        return {
            f"{prefix}_eligible": len(items),
            f"{prefix}_retrieved_mean_coverage_at_5": (
                sum(r["retrieved_point_coverage_at_5"] for r in items) / len(items) if items else None
            ),
            f"{prefix}_retrieved_fully_covered_at_5_count": sum(r["retrieved_all_points_covered_at_5"] for r in items),
            f"{prefix}_selected_mean_coverage": (
                sum(r["selected_point_coverage"] for r in items) / len(items) if items else None
            ),
            f"{prefix}_selected_fully_covered_count": sum(r["selected_all_points_covered"] for r in items),
        }
    return {**aggregate(eligible, "evidence_points"), **aggregate(multi, "multi_source_evidence_points")}


def load_manual_answer_reviews(path: Path | None, cases: list[dict]) -> dict[str, dict]:
    """Human labels must be recorded separately from retrieved evidence labels.

    Format per JSONL row: {"id":"q01", "point_correct":[true,false], "notes":"..."}.
    An omitted file means answer quality is unscored, not perfect.
    """
    if path is None:
        return {}
    cases_by_id = {case["id"]: case for case in cases}
    reviews = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        review = json.loads(line)
        cid = review.get("id")
        if cid not in cases_by_id or cid in reviews:
            raise ValueError(f"Unknown or duplicate review ID: {cid!r}")
        scores = review.get("point_correct")
        if (not isinstance(scores, list)
                or len(scores) != len(cases_by_id[cid]["expected_points"])
                or any(type(x) is not bool for x in scores)):
            raise ValueError(f"{cid}: point_correct needs one true/false per expected_points entry")
        reviews[cid] = review
    return reviews


def summarize_manual_reviews(records: list[dict]) -> dict:
    reviewed = [r for r in records if r["manual_answer_point_coverage"] is not None]
    answerable = [r for r in reviewed if r["category"] != "unsupported"]
    return {
        "manual_reviewed_cases": len(reviewed),
        "manual_reviewed_answerable_cases": len(answerable),
        "manual_answerable_mean_point_coverage": (
            sum(r["manual_answer_point_coverage"] for r in answerable) / len(answerable)
            if answerable else None
        ),
        "manual_answerable_fully_correct_count": sum(r["manual_answer_all_points_correct"] for r in answerable),
    }