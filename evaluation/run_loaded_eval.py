from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import time

from langchain_core.callbacks.base import BaseCallbackHandler

from src.graph import create_agent_graph
from src.rag.index import DEFAULT_CHUNKS, DocumentationIndex
from src.rag.ingestion import PROJECT_ROOT
from src.rag.subgraph import create_rag_subgraph
from src.tools.calculator import calculator
from src.tools.search import create_search_documentation_tool


# Fixed mixture; each question is run ten times in the default scenario.
# Expected statuses detect failures of routing, not answer correctness.
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
    ("What is my company’s logging retention policy?", "abstained"),
]


class TimedTool:
    """Measure cumulative tool time within a single serial graph invocation."""

    def __init__(self, tool):
        self.tool = tool
        self.seconds = 0.0
        self.calls = 0

    def reset(self):
        self.seconds = 0.0
        self.calls = 0

    def invoke(self, arguments):
        self.calls += 1
        started = time.perf_counter()
        try:
            return self.tool.invoke(arguments)
        finally:
            self.seconds += time.perf_counter() - started


class GenerationTimer(BaseCallbackHandler):
    """Time only the main graph's generate_answer node via LangGraph callbacks.

    Node callback intervals include framework boundary and callback overhead.
    A serial benchmark uses a fresh handler for each request.
    """

    def __init__(self):
        super().__init__()
        self.started = {}
        self.seconds = 0.0
        self.calls = 0

    def on_chain_start(self, serialized, inputs, *, run_id, tags=None, metadata=None, **kwargs):
        if (kwargs.get("name") == "generate_answer"
                and (metadata or {}).get("langgraph_node") == "generate_answer"
                and any(tag.startswith("graph:step:") for tag in (tags or []))):
            self.started[run_id] = time.perf_counter()
            self.calls += 1

    def _finish(self, run_id):
        started = self.started.pop(run_id, None)
        if started is not None:
            self.seconds += time.perf_counter() - started

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self._finish(run_id)

    def on_chain_error(self, error, *, run_id, **kwargs):
        self._finish(run_id)


def summary(values: list[float]) -> dict:
    """Summarize milliseconds; p95 uses the nearest-rank definition."""
    if not values:
        return {"count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None, "max_ms": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "mean_ms": statistics.mean(values),
        "median_ms": statistics.median(values),
        "p95_ms": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "max_ms": ordered[-1],
    }


def generation_timing_error(status: str | None, timer: GenerationTimer) -> str | None:
    """Reject silent callback failures for the known workflow's execution paths."""
    expected_calls = (
        1 if status in {"answered", "partial"} else 0
    )
    if timer.calls != expected_calls or timer.started:
        return ("generation timing incomplete: "
                f"status={status!r}, expected_calls={expected_calls}, "
                f"observed_calls={timer.calls}, unfinished={len(timer.started)}")
    return None


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _cpu_model() -> str | None:
    info = _read_text("/proc/cpuinfo") or ""
    for line in info.splitlines():
        if line.startswith("model name"):
            return line.partition(":")[2].strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/load.json"))
    args = parser.parse_args()
    if args.requests < 1 or args.warmup < 0:
        parser.error("--requests must be positive and --warmup must be non-negative")

    # Build/load and compilation are intentionally outside the measured window.
    index = DocumentationIndex()
    retrieval = TimedTool(create_search_documentation_tool(create_rag_subgraph(index)))
    arithmetic = TimedTool(calculator)
    graph = create_agent_graph(retrieval, arithmetic)
    for i in range(args.warmup):
        graph.invoke({"question": QUESTIONS[i % len(QUESTIONS)][0]},
                     config={"callbacks": [GenerationTimer()]})

    records = []
    run_started = datetime.now(timezone.utc).isoformat()
    wall_start = time.perf_counter()
    for i in range(args.requests):
        question, expected_status = QUESTIONS[i % len(QUESTIONS)]
        retrieval.reset()
        arithmetic.reset()
        generation = GenerationTimer()
        started = time.perf_counter()
        try:
            result = graph.invoke({"question": question}, config={"callbacks": [generation]})
            status = result.get("status")
            search_error = result.get("search_error")
            error = None if status == expected_status and not search_error else f"unexpected status={status!r} or search_error={search_error!r}"
            error = error or generation_timing_error(status, generation)
            succeeded = error is None
        except Exception as exc:
            status, succeeded, error = None, False, f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        records.append({
            "request": i + 1, "question": question, "expected_status": expected_status,
            "status": status, "success": succeeded, "error": error,
            "latency_ms": elapsed * 1000,
            "retrieval_ms": retrieval.seconds * 1000,
            "retrieval_calls": retrieval.calls,
            "calculator_ms": arithmetic.seconds * 1000,
            "calculator_calls": arithmetic.calls,
            "generation_ms": generation.seconds * 1000 if generation.calls else None,
            "generation_calls": generation.calls,
            "non_tool_ms": max(0.0, elapsed - retrieval.seconds - arithmetic.seconds) * 1000,
            "other_ms": max(0.0, elapsed - retrieval.seconds - arithmetic.seconds - generation.seconds) * 1000,
        })
    wall_seconds = time.perf_counter() - wall_start
    successes = [record for record in records if record["success"]]
    failures = [record for record in records if not record["success"]]
    report = {
        "run_started_utc": run_started,
        "scenario": {
            "requests": args.requests, "warmup_requests": args.warmup, "concurrency": 1,
            "questions": [{"question": q, "expected_status": s} for q, s in QUESTIONS],
            "mode": "rule-based planner and extractive generator; no LLM",
            "scope": "graph.invoke only; shared loaded index and compiled graphs; excludes startup, HTTP, and UI",
            "instrumentation": "Tool wrappers time retrieval and calculator calls. LangGraph callbacks bound the generate_answer node, including boundary/callback overhead. Non-tool time includes generation; other time excludes generation and includes orchestration, other nodes and timing overhead. These are alternative breakdowns, not additive. No LLM is used.",
            "p95_method": "nearest rank on successful requests",
            "success_definition": "graph returned expected status without a search error and generation callback timing is complete; does not assess answer correctness",
        },
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "cpu_model": _cpu_model(), "logical_cpus": os.cpu_count(),
            "affinity_cpus": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "cgroup_cpu_max": _read_text("/sys/fs/cgroup/cpu.max"),
            "cgroup_memory_max_bytes": _read_text("/sys/fs/cgroup/memory.max"),
            "package_versions": {name: importlib.metadata.version(name) for name in ("langgraph", "langchain-core", "scikit-learn", "numpy", "scipy")},
            "chunks_sha256": hashlib.sha256(DEFAULT_CHUNKS.read_bytes()).hexdigest(),
            "chunk_count": len(index.chunks),
            "source_sha256": {
                str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in (
                    PROJECT_ROOT / "src/graph.py",
                    PROJECT_ROOT / "src/nodes.py",
                    PROJECT_ROOT / "src/config.py",
                    PROJECT_ROOT / "src/rag/subgraph.py",
                    PROJECT_ROOT / "src/rag/index.py",
                    PROJECT_ROOT / "src/tools/calculator.py",
                    PROJECT_ROOT / "src/generation/base.py",
                    PROJECT_ROOT / "src/generation/dummy.py",
                    PROJECT_ROOT / "src/generation/ollama.py",
                    Path(__file__).resolve(),
                )
            },
        },
        "results": {
            "success_count": len(successes), "failure_count": len(failures),
            "status_counts": dict(Counter(r["status"] or "exception" for r in records)),
            "failure_causes": dict(Counter(r["error"] for r in failures)),
            "total_wall_seconds": wall_seconds,
            "successful_requests_per_second": len(successes) / wall_seconds,
            "latency_successes": summary([r["latency_ms"] for r in successes]),
            "retrieval_per_calling_request": summary([r["retrieval_ms"] for r in successes if r["retrieval_calls"]]),
            "calculator_per_calling_request": summary([r["calculator_ms"] for r in successes if r["calculator_calls"]]),
            "generation_per_calling_request": summary([r["generation_ms"] for r in successes if r["generation_calls"]]),
            "non_tool_per_success": summary([r["non_tool_ms"] for r in successes]),
            "other_per_success": summary([r["other_ms"] for r in successes]),
            "sum_retrieval_ms": sum(r["retrieval_ms"] for r in successes),
            "sum_calculator_ms": sum(r["calculator_ms"] for r in successes),
            "sum_generation_ms": sum(r["generation_ms"] for r in successes if r["generation_calls"]),
            "sum_non_tool_ms": sum(r["non_tool_ms"] for r in successes),
            "sum_other_ms": sum(r["other_ms"] for r in successes),
        },
        "requests": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["results"], indent=2))
    print(f"Wrote {args.output}")
    if failures:
        raise SystemExit(1)