"""Focused tests for the three concepts used by the functional evaluator."""
import json

import pytest

from evaluation.point_metrics import evidence_coverage, load_reviews, validate_labels
from evaluation.run_eval import RecordingTool, mean, summarize


def test_evidence_coverage_accepts_alternative_chunks():
    requirements = [
        {"point": "first fact", "supporting_chunk_ids": ["a", "b"]},
        {"point": "second fact", "supporting_chunk_ids": ["c"]},
    ]
    assert evidence_coverage(requirements, ["b"]) == 0.5
    assert evidence_coverage(requirements, ["b", "c"]) == 1.0
    assert evidence_coverage(requirements, ["unrelated"]) == 0.0
    assert evidence_coverage([], ["a"]) is None  # Not a retrieval case.


def test_valid_gold_labels_and_rejects_unknown_ids():
    chunks = [{"chunk_id": "a", "document_id": "json"},
              {"chunk_id": "b", "document_id": "json"}]
    case = {
        "id": "q1", "category": "single_source", "expected_points": ["fact"],
        "expected_tools": ["search_documentation"],
        "required_evidence": [{"point": "fact", "supporting_chunk_ids": ["a", "b"]}],
        "relevant_chunk_ids": ["a", "b"],
    }
    validate_labels([case], chunks)
    with pytest.raises(ValueError, match="unknown supporting chunk IDs"):
        validate_labels([{**case, "required_evidence": [{"point": "fact", "supporting_chunk_ids": ["missing"]}]}], chunks)
    with pytest.raises(ValueError, match="disagrees"):
        validate_labels([{**case, "relevant_chunk_ids": ["a"]}], chunks)


def test_multi_source_requires_two_documents():
    chunks = [{"chunk_id": "a", "document_id": "json"},
              {"chunk_id": "b", "document_id": "json"}]
    case = {
        "id": "q2", "category": "multi_source", "expected_points": ["fact"],
        "expected_tools": ["search_documentation"],
        "required_evidence": [{"point": "fact", "supporting_chunk_ids": ["a", "b"]}],
        "relevant_chunk_ids": ["a", "b"],
    }
    with pytest.raises(ValueError, match="multi_source"):
        validate_labels([case], chunks)


def test_manual_answer_quality_is_unscored_without_human_review(tmp_path):
    cases = [{"id": "q01", "expected_points": ["a", "b"]}]
    assert load_reviews(None, cases) == {}
    reviews_file = tmp_path / "reviews.jsonl"
    reviews_file.write_text(json.dumps({"id": "q01", "point_correct": [True, False]}) + "\n")
    assert load_reviews(reviews_file, cases)["q01"]["point_correct"] == [True, False]
    reviews_file.write_text(json.dumps({"id": "q01", "point_correct": [1, 0]}) + "\n")
    with pytest.raises(ValueError, match="boolean"):
        load_reviews(reviews_file, cases)


def test_recording_tool_keeps_failed_calls():
    class FailingTool:
        def invoke(self, arguments):
            raise OSError("not available")

    recorder = RecordingTool(FailingTool())
    with pytest.raises(OSError):
        recorder.invoke({"query": "test"})
    assert recorder.calls == [{"result": None, "error": "OSError"}]


def test_summary_does_not_confuse_retrieval_with_answer_accuracy():
    example = {
        "category": "single_source", "error": None,
        "status_correct": True, "tools_correct": True,
        "evidence_coverage_at_5": 1.0,
        "selected_evidence_coverage": 1.0,
        "calculation_correct": None,
        "manual_answer_coverage": None,
    }
    stats = summarize([example])
    assert stats["fully_covered_at_5"] == 1
    assert stats["human_reviewed_cases"] == 0
    assert stats["human_answer_coverage"] is None
    assert mean([]) is None


def test_calculation_scoring_excludes_documentation_questions():
    """Only questions with an expected numeric result count as calculations."""
    from evaluation.run_eval import evaluate_case

    class FakeGraph:
        def invoke(self, state):
            if "12 * 7" in state["question"]:
                return {"status": "answered", "calculation_result": {"result": 84}}
            return {"status": "answered"}

    class Recorder:
        calls = []

    base = {
        "id": "q01",
        "category": "single_source",
        "question": "What does json.dumps do?",
        "expected_status": "answered",
        "expected_tools": [],
        "expected_calculation": None,
        "required_evidence": [],
    }
    docs = evaluate_case(base, FakeGraph(), Recorder(), Recorder(), None)
    arithmetic = evaluate_case(
        {**base, "id": "q10", "category": "calculation",
         "question": "What is 12 * 7?", "expected_calculation": 84},
        FakeGraph(), Recorder(), Recorder(), None,
    )
    assert docs["calculation_correct"] is None
    assert arithmetic["calculation_correct"] is True
    stats = summarize([docs, arithmetic])
    assert stats["calculation_cases"] == 1
    assert stats["calculations_correct"] == 1
