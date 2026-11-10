import json

import streamlit as st
import pytest
from streamlit.testing.v1 import AppTest

from src.rag import index as index_module
from src.rag.ingestion import PROJECT_ROOT, ingest


@pytest.fixture
def isolated_index(tmp_path, monkeypatch):
    chunks = tmp_path / "chunks.jsonl"
    index_dir = tmp_path / "index"
    ingest(PROJECT_ROOT / "data/sources.json", chunks)
    index_module.build_index(chunks, index_dir)
    monkeypatch.setattr(index_module, "DEFAULT_CHUNKS", chunks)
    monkeypatch.setattr(index_module, "DEFAULT_INDEX", index_dir)
    st.cache_resource.clear()
    yield chunks, index_dir
    st.cache_resource.clear()

@pytest.fixture(autouse=True)
def dummy_generator_for_ui_tests(monkeypatch):
    monkeypatch.setenv("RAG_GENERATOR", "dummy")


def test_chat_returns_cited_answer_evidence_and_ordered_trace(isolated_index):
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    assert not app.exception

    app.chat_input[0].set_value("What does json.dumps do?").run(timeout=10)

    assert not app.exception
    messages = app.session_state["messages"]
    assert messages[0] == {"role": "user", "content": "What does json.dumps do?"}
    result = messages[1]["result"]
    assert result["status"] == "answered"
    assert "json.dumps" in result["answer"]
    assert result["citations"] and "json.html" in result["citations"][0]["source_url"]
    assert result["documents"] and result["documents"][0]["text"]
    assert [event["node"] for event in result["trace"]] == [
        "plan", "retrieve", "assess_evidence", "generate_answer", "finalize"
    ]
    assert [item.label for item in app.expander] == [
        "Sources", "Retrieved evidence", "Workflow trace"
    ]
    assert any("json.dumps" in item.value for item in app.markdown)
    assert any("json.html" in item.value for item in app.markdown)
    assert any("json.dumps" in item.value for item in app.text)
    trace_items = [item.value for item in app.markdown if "plan:" in item.value or "finalize:" in item.value]
    assert len(trace_items) == 2 and "plan:" in trace_items[0] and "finalize:" in trace_items[1]

    app.chat_input[0].set_value("What is 12 * 7?").run(timeout=10)
    assert not app.exception
    messages = app.session_state["messages"]
    assert len(messages) == 4
    assert messages[1]["result"]["citations"]
    assert messages[3]["result"]["calculation_result"]["result"] == 84

    app.button[0].click().run(timeout=10)
    assert not app.exception
    assert app.session_state["messages"] == []


def test_missing_index_shows_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(index_module, "DEFAULT_CHUNKS", tmp_path / "missing.jsonl")
    monkeypatch.setattr(index_module, "DEFAULT_INDEX", tmp_path / "missing-index")
    st.cache_resource.clear()
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    app.chat_input[0].set_value("What does json.dumps do?").run(timeout=10)

    assert not app.exception
    assert len(app.error) == 1
    assert "index" in app.error[0].value.lower()
    assert any("src.rag.ingestion" in code.value for code in app.code)
    assert app.session_state["messages"][-1]["setup_required"] is True


def test_workflow_failure_displays_generic_error(isolated_index, monkeypatch):
    from src import graph

    class BrokenAgent:
        def invoke(self, state):
            raise RuntimeError("sensitive internal details")

    monkeypatch.setattr(graph, "create_agent_graph", lambda *args: BrokenAgent())
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    app.chat_input[0].set_value("What does json.dumps do?").run(timeout=10)

    assert not app.exception
    assert len(app.error) == 1
    assert "could not be processed" in app.error[0].value.lower()
    assert "sensitive internal details" not in app.error[0].value
    assert app.session_state["messages"][-1]["role"] == "assistant"