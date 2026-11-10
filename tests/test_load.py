"""The load test uses straightforward timing wrappers, not graph callbacks."""
import pytest

from evaluation.run_loaded_eval import TimedGenerator, TimedTool, latency_stats


def test_timed_tool_counts_calls_and_does_not_change_results():
    class FakeTool:
        def invoke(self, arguments):
            return arguments["value"] * 2

    tool = TimedTool(FakeTool())
    assert tool.invoke({"value": 7}) == 14
    assert tool.calls == 1
    assert tool.seconds >= 0
    tool.reset()
    assert tool.calls == 0
    assert tool.seconds == 0


def test_timed_generator_returns_normal_dummy_result():
    generator = TimedGenerator()
    result = generator.generate("What is Python?", [{"text": "Python is a programming language.", "source_url": "source"}])
    assert result.backend == "dummy"
    assert generator.calls == 1
    assert generator.seconds >= 0
    generator.reset()
    assert generator.calls == 0


def test_latency_stats_nearest_rank():
    assert latency_stats([])["p95_ms"] is None
    stats = latency_stats(list(range(1, 101)))
    assert stats["mean_ms"] == 50.5
    assert stats["p95_ms"] == 95
    assert stats["max_ms"] == 100
