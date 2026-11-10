"""Evaluate the deterministic agent on annotated Python documentation questions."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from evaluation.point_metrics import evidence_coverage, load_reviews, validate_labels
from src.generation.dummy import DummyGenerator
from src.graph import create_agent_graph
from src.rag.index import DocumentationIndex, build_index
from src.rag.ingestion import PROJECT_ROOT, ingest
from src.rag.subgraph import create_rag_subgraph
from src.tools.calculator import calculator
from src.tools.search import create_search_documentation_tool


class RecordingTool:
    """Record the result of every tool call without changing the tool."""

    def __init__(self, tool):
        self.tool = tool
        self.calls = []

    def invoke(self, arguments):
        call = {"result": None, "error": None}
        self.calls.append(call)
        try:
            call["result"] = self.tool.invoke(arguments)
            return call["result"]
        except Exception as exc:
            call["error"] = type(exc).__name__
            raise


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def evaluate_case(case: dict, graph, search: RecordingTool, calc: RecordingTool, review: dict | None) -> dict:
    """Run one question and compare the observable result with the gold labels."""
    search.calls.clear()
    calc.calls.clear()
    error = None
    try:
        state = graph.invoke({"question": case["question"]})
    except Exception as exc:
        state, error = {}, f"{type(exc).__name__}: {exc}"

    tools = []
    if search.calls:
        tools.append("search_documentation")
    if calc.calls:
        tools.append("calculate")
    first = search.calls[0]["result"] if search.calls else None
    first_ids = [doc["chunk_id"] for doc in first.get("documents", [])[:5]] if first else []
    selected_ids = [doc["chunk_id"] for doc in state.get("documents", [])]
    first_coverage = evidence_coverage(case["required_evidence"], first_ids)
    selected_coverage = evidence_coverage(case["required_evidence"], selected_ids)
    calculation = state.get("calculation_result")
    expected_calculation = case.get("expected_calculation")
    reviewed_points = review["point_correct"] if review else None
    review_score = mean(reviewed_points) if reviewed_points is not None else None
    return {
        "id": case["id"], "category": case["category"], "question": case["question"],
        "status": state.get("status"), "expected_status": case["expected_status"],
        "status_correct": error is None and not state.get("search_error") and state.get("status") == case["expected_status"],
        "tools": tools, "expected_tools": case["expected_tools"],
        "tools_correct": error is None and set(tools) == set(case["expected_tools"]),
        "retrieved_chunk_ids": first_ids, "selected_chunk_ids": selected_ids,
        "evidence_coverage_at_5": first_coverage,
        "selected_evidence_coverage": selected_coverage,
        "calculation_correct": (
            calculation is not None and calculation.get("result") == expected_calculation
        ) if expected_calculation is not None else None,
        "answer": state.get("answer", ""),
        "citations": state.get("citations", []),
        "manual_answer_coverage": review_score,
        "manual_notes": review.get("notes", "") if review else None,
        "error": error or state.get("search_error"),
    }


def summarize(records: list[dict]) -> dict:
    """One main retrieval metric; independent counts for other agent behaviors."""
    evidence = [r for r in records if r["evidence_coverage_at_5"] is not None]
    multi = [r for r in evidence if r["category"] == "multi_source"]
    calculations = [r for r in records if r["calculation_correct"] is not None]
    reviewed = [r for r in records if r["manual_answer_coverage"] is not None]
    reviewed_answerable = [r for r in reviewed if r["category"] != "unsupported"]
    return {
        "questions": len(records),
        "errors": sum(r["error"] is not None for r in records),
        "status_correct": sum(r["status_correct"] for r in records),
        "tool_selection_correct": sum(r["tools_correct"] for r in records),
        "evidence_cases": len(evidence),
        "mean_evidence_coverage_at_5": mean([r["evidence_coverage_at_5"] for r in evidence]),
        "fully_covered_at_5": sum(r["evidence_coverage_at_5"] == 1 for r in evidence),
        "mean_selected_evidence_coverage": mean([r["selected_evidence_coverage"] for r in evidence]),
        "fully_covered_selected": sum(r["selected_evidence_coverage"] == 1 for r in evidence),
        "multi_source_cases": len(multi),
        "multi_source_fully_covered_at_5": sum(r["evidence_coverage_at_5"] == 1 for r in multi),
        "calculation_cases": len(calculations),
        "calculations_correct": sum(r["calculation_correct"] for r in calculations),
        "human_reviewed_cases": len(reviewed),
        "human_answer_coverage": mean([r["manual_answer_coverage"] for r in reviewed_answerable]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "evaluation/development_questions.jsonl")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "evaluation/results/functional.json")
    parser.add_argument("--reviews", type=Path, help="Optional human answer review JSONL")
    args = parser.parse_args()

    dataset_bytes = args.dataset.read_bytes()
    cases = [json.loads(line) for line in dataset_bytes.decode("utf-8").splitlines() if line.strip()]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Question dataset must contain unique, nonempty IDs")
    reviews = load_reviews(args.reviews, cases)

    # Rebuild a fresh index so the test does not rely on a cached local index.
    with tempfile.TemporaryDirectory(prefix="rag-eval-") as tmp:
        chunks_path = Path(tmp) / "chunks.jsonl"
        index_dir = Path(tmp) / "index"
        ingest(PROJECT_ROOT / "data/sources.json", chunks_path)
        build_index(chunks_path, index_dir)
        index = DocumentationIndex(chunks_path, index_dir)
        validate_labels(cases, index.chunks)

        search = RecordingTool(create_search_documentation_tool(create_rag_subgraph(index, k=5)))
        calc = RecordingTool(calculator)
        graph = create_agent_graph(search, calc, DummyGenerator())
        records = [evaluate_case(case, graph, search, calc, reviews.get(case["id"])) for case in cases]
        report = {
            "method": "Retrieval = fraction of annotated answer points with any supporting chunk among the first 5 results. This is NOT final answer correctness. The generator is deterministic (no Ollama).",
            "config": {
                "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
                "chunks_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
                "chunk_count": len(index.chunks), "top_k": 5,
                "generator": "dummy",
            },
            "summary": summarize(records), "cases": records,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
