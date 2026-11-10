"""Run a serial load test of the deterministic LangGraph workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from src.generation.dummy import DummyGenerator
from src.graph import create_agent_graph
from src.rag.index import DEFAULT_CHUNKS, DocumentationIndex
from src.rag.ingestion import PROJECT_ROOT
from src.rag.subgraph import create_rag_subgraph
from src.tools.calculator import calculator
from src.tools.search import create_search_documentation_tool


# Repeat these ten examples in order to reach the requested number of calls.
QUESTIONS = [
    ("What does json.dumps do?", "answered"),
    ("What does json.dump do?", "answered"),
    ("How do I read a text file using pathlib?", "answered"),
    ("How do I create a virtual environment?", "answered"),
    ("What does logging.exception do?", "answered"),
    ("How does csv.reader work?", "answered"),
    ("What is 12 * 7?", "answered"),
    ("Calculate 18 / 3", "answered"),
    ("What does json.dumps do and what is 12 * 7?", "answered"),
    ("What is my company's logging retention policy?", "abstained"),
]


class TimedTool:
    """Simple wrapper: measure how much time a tool spends running."""

    def __init__(self, tool):
        self.tool = tool
        self.seconds = 0.0
        self.calls = 0

    def reset(self):
        self.seconds, self.calls = 0.0, 0

    def invoke(self, arguments):
        self.calls += 1
        started = time.perf_counter()
        try:
            return self.tool.invoke(arguments)
        finally:
            self.seconds += time.perf_counter() - started


class TimedGenerator:
    """Measure the dummy generator directly, without LangGraph callbacks."""

    def __init__(self):
        self.generator = DummyGenerator()
        self.seconds = 0.0
        self.calls = 0

    def reset(self):
        self.seconds, self.calls = 0.0, 0

    def generate(self, question: str, documents: list[dict]):
        self.calls += 1
        started = time.perf_counter()
        try:
            return self.generator.generate(question, documents)
        finally:
            self.seconds += time.perf_counter() - started


def latency_stats(milliseconds: list[float]) -> dict:
    """Mean and nearest-rank p95, calculated on successful requests only."""
    if not milliseconds:
        return {"mean_ms": None, "p95_ms": None, "max_ms": None}
    ordered = sorted(milliseconds)
    return {
        "mean_ms": statistics.mean(ordered),
        "p95_ms": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "max_ms": ordered[-1],
    }


def run_request(question: str, expected_status: str, graph, search, calc, generator) -> dict:
    """Run one request and record overall latency and measured component time."""
    search.reset()
    calc.reset()
    generator.reset()
    started = time.perf_counter()
    try:
        result = graph.invoke({"question": question})
        status = result.get("status")
        error = None if status == expected_status and not result.get("search_error") else f"unexpected status: {status}"
    except Exception as exc:
        status, error = None, f"{type(exc).__name__}: {exc}"
    elapsed_ms = (time.perf_counter() - started) * 1000
    retrieval_ms = search.seconds * 1000
    calculator_ms = calc.seconds * 1000
    generator_ms = generator.seconds * 1000
    return {
        "question": question, "expected_status": expected_status, "status": status,
        "success": error is None, "error": error,
        "latency_ms": elapsed_ms,
        "retrieval_ms": retrieval_ms, "calculator_ms": calculator_ms,
        "generator_ms": generator_ms,
        "other_ms": max(0.0, elapsed_ms - retrieval_ms - calculator_ms - generator_ms),
        "retrieval_calls": search.calls, "calculator_calls": calc.calls,
        "generator_calls": generator.calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "evaluation/results/load.json")
    args = parser.parse_args()
    if args.requests < 1 or args.warmup < 0:
        parser.error("--requests must be positive and --warmup nonnegative")

    # Index loading and graph compilation are excluded from request timings.
    index = DocumentationIndex()
    search = TimedTool(create_search_documentation_tool(create_rag_subgraph(index)))
    calc = TimedTool(calculator)
    generator = TimedGenerator()
    graph = create_agent_graph(search, calc, generator)

    for i in range(args.warmup):
        graph.invoke({"question": QUESTIONS[i % len(QUESTIONS)][0]})

    started = time.perf_counter()
    records = []
    for i in range(args.requests):
        question, status = QUESTIONS[i % len(QUESTIONS)]
        records.append(run_request(question, status, graph, search, calc, generator))
        if (i + 1) % 10 == 0 or i == args.requests - 1:
            print(f"Completed {i + 1}/{args.requests} requests", flush=True)
    wall_seconds = time.perf_counter() - started
    successful = [record for record in records if record["success"]]
    failures = [record for record in records if not record["success"]]

    tracked_files = ["src/graph.py", "src/nodes.py", "src/rag/querying.py",
                     "src/rag/subgraph.py", "src/generation/dummy.py",
                     "src/rag/index.py", "evaluation/run_loaded_eval.py"]
    report = {
        "run_started_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "requests": args.requests, "warmup": args.warmup, "concurrency": 1,
            "generator": "dummy (no Ollama)",
            "scope": "Sequential graph.invoke; excludes startup, Streamlit and HTTP",
            "success_definition": "Correct status and no search error; does not measure answer correctness",
            "timing_note": "generator_ms measures only DummyGenerator.generate; other_ms includes LangGraph and answer formatting",
        },
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "chunks_sha256": hashlib.sha256(DEFAULT_CHUNKS.read_bytes()).hexdigest(),
            "code_sha256": {filename: hashlib.sha256((PROJECT_ROOT / filename).read_bytes()).hexdigest()
                            for filename in tracked_files},
        },
        "results": {
            "success_count": len(successful), "failure_count": len(failures),
            "requests_per_second": len(successful) / wall_seconds if wall_seconds else None,
            "latency": latency_stats([r["latency_ms"] for r in successful]),
            "retrieval": latency_stats([r["retrieval_ms"] for r in successful if r["retrieval_calls"]]),
            "calculator": latency_stats([r["calculator_ms"] for r in successful if r["calculator_calls"]]),
            "generator": latency_stats([r["generator_ms"] for r in successful if r["generator_calls"]]),
            "other": latency_stats([r["other_ms"] for r in successful]),
        },
        "requests": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["results"], indent=2))
    print(f"Saved {args.output}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
