from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import tempfile
from pathlib import Path

from evaluation.point_metrics import (
    load_manual_answer_reviews, score_evidence_points,
    summarize_manual_reviews, summarize_point_metrics, validate_required_evidence,
)
from src.graph import create_agent_graph
from src.rag.index import DocumentationIndex, build_index
from src.rag.ingestion import PROJECT_ROOT, ingest
from src.rag.subgraph import create_rag_subgraph
from src.tools.calculator import calculator
from src.tools.search import create_search_documentation_tool


class RecordingTool:
    def __init__(self, tool):
        self.tool = tool
        self.calls = []

    def invoke(self, arguments):
        call = {"arguments": arguments.copy(), "result": None, "error": None}
        self.calls.append(call)
        try:
            call["result"] = self.tool.invoke(arguments)
            return call["result"]
        except Exception as exc:
            call["error"] = type(exc).__name__
            raise


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_chunk_labels(cases: list[dict], chunks: list[dict]) -> None:
    """Reject duplicate or unknown labels, showing same-source chunks for diagnosis."""
    known_ids = {chunk["chunk_id"] for chunk in chunks}
    for case in cases:
        labels = case["relevant_chunk_ids"]
        duplicates = sorted({label for label in labels if labels.count(label) > 1})
        missing = sorted(set(labels) - known_ids)
        if not duplicates and not missing:
            continue

        details = [f"Invalid relevant_chunk_ids for {case['id']}:"]
        if duplicates:
            details.append(f"  Duplicate IDs: {duplicates}")
        if missing:
            details.append(f"  IDs not found in the generated corpus: {missing}")
            source_ids = {label.split('--', 1)[0] for label in missing if '--' in label}
            candidates = [chunk for chunk in chunks if chunk.get("document_id") in source_ids]
            if candidates:
                details.append("  Available chunks from the same source(s):")
                for chunk in candidates[:20]:
                    details.append(f"    {chunk['chunk_id']} | section: {chunk.get('section', '')}")
                if len(candidates) > 20:
                    details.append(f"    ... and {len(candidates) - 20} more")
            else:
                details.append("  No generated chunks matched the missing IDs' source prefixes.")
            details.append("  Check the manifest, source headings and ingestion version; "
                           "only relabel after verifying that the replacement supports the expected answer.")
        raise ValueError("\n".join(details))


def score_retrieval(relevant_ids: list[str], retrieved_ids: list[str]) -> dict:
    """Measure first-call retrieval; unlabeled cases have no recall denominator."""
    relevant = set(relevant_ids)
    if not relevant:
        return {"hit_at_5": None, "recall_at_5": None, "all_relevant_at_5": None}
    matched = relevant.intersection(retrieved_ids)
    return {
        "hit_at_5": bool(matched),
        "recall_at_5": len(matched) / len(relevant),
        "all_relevant_at_5": matched == relevant,
    }


def score_sources(relevant_ids: list[str], retrieved_ids: list[str], chunk_sources: dict[str, str]) -> dict:
    """Score distinct source documents represented by labeled/retrieved chunks.

    Two labeled sections can belong to the same source; chunk recall is still
    reported separately to expose missing sections within that document.
    """
    relevant = {chunk_sources[chunk_id] for chunk_id in relevant_ids}
    retrieved = {chunk_sources[chunk_id] for chunk_id in retrieved_ids}
    if not relevant:
        return {"relevant_source_ids": [], "retrieved_source_ids": sorted(retrieved),
                "source_recall_at_5": None, "all_sources_at_5": None}
    matched = relevant & retrieved
    return {"relevant_source_ids": sorted(relevant), "retrieved_source_ids": sorted(retrieved),
            "source_recall_at_5": len(matched) / len(relevant),
            "all_sources_at_5": matched == relevant}


def summarize_sources(records: list[dict]) -> dict:
    """Macro-average per-question recall over cases with labeled sources."""
    eligible = [r for r in records if r["source_recall_at_5"] is not None]
    multi = [r for r in eligible if r["category"] == "multi_source"]
    def metrics(items: list[dict], prefix: str) -> dict:
        return {
            f"{prefix}_eligible": len(items),
            f"{prefix}_mean_recall_at_5": sum(r["source_recall_at_5"] for r in items) / len(items) if items else None,
            f"{prefix}_all_relevant_at_5_count": sum(r["all_sources_at_5"] for r in items),
        }
    return {**metrics(eligible, "source_retrieval"), **metrics(multi, "multi_source_document_retrieval")}


def summarize_retrieval(records: list[dict]) -> dict:
    """Aggregate only labeled cases, including multi-section-specific coverage."""
    eligible = [r for r in records if r["hit_at_5"] is not None]
    multi = [r for r in eligible if r["category"] == "multi_source"]
    return {
        "retrieval_eligible": len(eligible),
        "retrieval_hit_at_5_count": sum(r["hit_at_5"] for r in eligible),
        "retrieval_mean_recall_at_5": sum(r["recall_at_5"] for r in eligible) / len(eligible) if eligible else None,
        "retrieval_all_relevant_at_5_count": sum(r["all_relevant_at_5"] for r in eligible),
        "multi_source_retrieval_eligible": len(multi),
        "multi_source_hit_at_5_count": sum(r["hit_at_5"] for r in multi),
        "multi_source_all_relevant_at_5_count": sum(r["all_relevant_at_5"] for r in multi),
        "multi_source_mean_recall_at_5": sum(r["recall_at_5"] for r in multi) / len(multi) if multi else None,
        "selected_eligible": len(eligible),
        "selected_hit_count": sum(r["selected_hit"] for r in eligible),
        "selected_mean_recall": sum(r["selected_recall"] for r in eligible) / len(eligible) if eligible else None,
        "selected_all_relevant_count": sum(r["selected_all_relevant"] for r in eligible),
        "multi_source_selected_eligible": len(multi),
        "multi_source_selected_hit_count": sum(r["selected_hit"] for r in multi),
        "multi_source_selected_mean_recall": sum(r["selected_recall"] for r in multi) / len(multi) if multi else None,
        "multi_source_selected_all_relevant_count": sum(r["selected_all_relevant"] for r in multi),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "evaluation/development_questions.jsonl")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "evaluation/results/functional.json")
    parser.add_argument(
        "--reviews", type=Path, default=None,
        help="Optional independently completed manual answer review JSONL",
    )
    args = parser.parse_args()
    raw_dataset = args.dataset.read_bytes()
    cases = [json.loads(line) for line in raw_dataset.decode("utf-8").splitlines() if line.strip()]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("dataset must be nonempty and contain unique case ids")
    manual_reviews = load_manual_answer_reviews(args.reviews, cases)

    with tempfile.TemporaryDirectory(prefix="rag-evaluation-") as tmp:
        chunks, index_dir = Path(tmp) / "chunks.jsonl", Path(tmp) / "index"
        count = ingest(PROJECT_ROOT / "data/sources.json", chunks)
        build_index(chunks, index_dir)
        index = DocumentationIndex(chunks, index_dir)
        chunk_sources = {chunk["chunk_id"]: chunk["document_id"] for chunk in index.chunks}
        validate_chunk_labels(cases, index.chunks)
        validate_required_evidence(cases, index.chunks)
        search = RecordingTool(create_search_documentation_tool(create_rag_subgraph(index, k=5)))
        calc = RecordingTool(calculator)
        graph = create_agent_graph(search, calc)
        results = []
        for case in cases:
            search.calls.clear()
            calc.calls.clear()
            error = None
            try:
                state = graph.invoke({"question": case["question"]})
            except Exception as exc:
                state = {}
                error = f"{type(exc).__name__}: {exc}"
            actual_tools = (["search_documentation"] if search.calls else []) + (["calculate"] if calc.calls else [])
            first_result = search.calls[0]["result"] if search.calls else None
            retrieved = first_result["documents"] if first_result is not None else []
            ids = [doc["chunk_id"] for doc in retrieved][:5]
            calculation = state.get("calculation_result")
            answer = state.get("answer", "")
            search_error = state.get("search_error")
            selected_ids = [doc["chunk_id"] for doc in state.get("documents", [])]
            selected_score = score_retrieval(case["relevant_chunk_ids"], selected_ids)
            retrieved_points = score_evidence_points(case["required_evidence"], ids)
            selected_points = score_evidence_points(case["required_evidence"], selected_ids)
            review = manual_reviews.get(case["id"])
            manual_scores = review["point_correct"] if review is not None else None
            manual_coverage = (sum(manual_scores) / len(manual_scores)) if manual_scores else None
            results.append({
                "id": case["id"], "category": case["category"], "question": case["question"],
                "expected_points": case["expected_points"], "expected_status": case["expected_status"],
                "expected_tools": case["expected_tools"], "expected_calculation": case.get("expected_calculation"),
                "relevant_chunk_ids": case["relevant_chunk_ids"], "first_retrieval_ids": ids,
                **score_retrieval(case["relevant_chunk_ids"], ids),
                **score_sources(case["relevant_chunk_ids"], ids, chunk_sources),
                "selected_chunk_ids": selected_ids,
                "required_evidence": case["required_evidence"],
                "retrieved_point_coverage_at_5": retrieved_points["point_coverage"],
                "retrieved_all_points_covered_at_5": retrieved_points["all_points_covered"],
                "retrieved_covered_points_at_5": retrieved_points["covered_points"],
                "selected_point_coverage": selected_points["point_coverage"],
                "selected_all_points_covered": selected_points["all_points_covered"],
                "selected_covered_points": selected_points["covered_points"],
                "manual_answer_point_coverage": manual_coverage,
                "manual_answer_all_points_correct": (all(manual_scores) if manual_scores is not None else None),
                "manual_answer_review_notes": review.get("notes", "") if review else None,
                "selected_hit": selected_score["hit_at_5"],
                "selected_recall": selected_score["recall_at_5"],
                "selected_all_relevant": selected_score["all_relevant_at_5"],
                "status": state.get("status"), "status_matches": state.get("status") == case["expected_status"] and not search_error,
                "actual_tools": actual_tools, "tools_match": set(actual_tools) == set(case["expected_tools"]),
                "calculation_result": calculation,
                "calculation_matches": (calculation is not None and calculation.get("result") == case["expected_calculation"]) if "expected_calculation" in case else None,
                "answer": answer, "answer_sha256": digest(answer.encode("utf-8")),
                "citations": state.get("citations", []), "selected_documents": state.get("documents", []),
                "trace": state.get("trace", []), "error": error, "search_error": search_error,
                "search_attempts": len(search.calls),
                "search_attempt_errors": [call["error"] for call in search.calls if call["error"]],
            })
        calculation_cases = [r for r in results if r["calculation_matches"] is not None]
        summary = {
            "questions": len(results),
            "errors": sum(r["error"] is not None or r["search_error"] is not None for r in results),
            "category_counts": {category: sum(r["category"] == category for r in results) for category in sorted({r["category"] for r in results})},
            "expected_status_matches": sum(r["status_matches"] for r in results),
            "tool_selection_matches": sum(r["tools_match"] for r in results),
            **summarize_retrieval(results),
            **summarize_sources(results),
            **summarize_point_metrics(results),
            **summarize_manual_reviews(results),
            "calculation_eligible": len(calculation_cases), "calculation_matches": sum(r["calculation_matches"] for r in calculation_cases),
        }
        report = {
            "method": "Primary metric: per-point evidence coverage, OR over independently validated alternative chunks within each point, AND across required points. First-call coverage uses first five retrieved chunks, selected coverage uses final graph documents. Calculation, tool selection, status and separately human-reviewed answer quality are different metrics. Older chunk and source recall are diagnostic only; they penalize missed alternative chunks. A status match is not proof of answer correctness.",
            "config": {"dataset_sha256": digest(raw_dataset), "chunks_sha256": digest(chunks.read_bytes()), "chunks": count,
                       "python": platform.python_version(), "platform": platform.platform(),
                       "langgraph": importlib.metadata.version("langgraph"), "scikit_learn": importlib.metadata.version("scikit-learn"),
                       "k": 5, "min_score": 0.0, "generator": "deterministic extractive baseline; no LLM",
                       "annotation_schema": "answer-point-evidence-v1",
                       "manual_review_sha256": digest(args.reviews.read_bytes()) if args.reviews else None},
            "summary": summary, "cases": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
