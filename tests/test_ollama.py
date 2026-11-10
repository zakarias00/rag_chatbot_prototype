import requests
import streamlit as st
import pytest
from streamlit.testing.v1 import AppTest

from src.config import create_generator, load_settings
from src.graph import create_agent_graph
from src.rag import index as index_module
from src.rag.ingestion import PROJECT_ROOT, ingest
from src.rag.subgraph import create_rag_subgraph
from src.tools.calculator import calculator
from src.tools.search import create_search_documentation_tool


@pytest.fixture
def search_and_index(tmp_path, monkeypatch):
    chunks = tmp_path / "chunks.jsonl"
    index_dir = tmp_path / "index"
    ingest(PROJECT_ROOT / "data/sources.json", chunks)
    index_module.build_index(chunks, index_dir)
    monkeypatch.setattr(index_module, "DEFAULT_CHUNKS", chunks)
    monkeypatch.setattr(index_module, "DEFAULT_INDEX", index_dir)
    index = index_module.DocumentationIndex(chunks, index_dir)
    st.cache_resource.clear()
    yield create_search_documentation_tool(create_rag_subgraph(index, k=5))
    st.cache_resource.clear()


class SuccessfulResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": "json.dumps returns a JSON string [1]."}}


def test_real_graph_calls_configured_ollama_and_keeps_calculation_and_citation(
    search_and_index, monkeypatch
):
    from src.generation import ollama

    requests_seen = []

    def post(url, *, json, timeout):
        requests_seen.append((url, json, timeout))
        return SuccessfulResponse()

    monkeypatch.setattr(ollama.requests, "post", post)
    monkeypatch.setenv("RAG_GENERATOR", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:12345")
    monkeypatch.setenv("OLLAMA_MODEL", "local-test-model")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "15")
    graph = create_agent_graph(search_and_index, calculator, create_generator(load_settings()))

    result = graph.invoke({"question": "What does json.dumps do and what is 12 * 7?"})

    assert result["status"] == "answered"
    assert result["generation_backend"] == "ollama"
    assert result["generation_fallback_reason"] is None
    assert result["calculation_result"]["result"] == 84
    assert "84" in result["answer"] and "JSON string" in result["answer"]
    assert result["citations"] and "json.html" in result["citations"][0]["source_url"]
    assert len(requests_seen) == 1
    url, payload, timeout = requests_seen[0]
    assert url == "http://localhost:12345/api/chat"
    assert payload["model"] == "local-test-model"
    assert payload["stream"] is False
    assert timeout == (2.0, 15.0)
    assert "json.dumps" in payload["messages"][-1]["content"]
    assert "12 * 7" not in payload["messages"][-1]["content"]


def test_real_graph_falls_back_on_unreachable_ollama_and_preserves_evidence(
    search_and_index, monkeypatch
):
    from src.generation import ollama

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(ollama.requests, "post", unavailable)
    monkeypatch.setenv("RAG_GENERATOR", "ollama")
    graph = create_agent_graph(search_and_index, calculator, create_generator())
    result = graph.invoke({"question": "What does json.dumps do?"})

    assert result["status"] == "answered"
    assert result["generation_backend"] == "dummy"
    assert result["generation_fallback_reason"]
    assert "json.dumps" in result["answer"]
    assert result["citations"] and "json.html" in result["citations"][0]["source_url"]
    assert any("fallback" in e["message"].lower() for e in result["trace"])


def test_calculation_and_no_evidence_never_call_ollama(search_and_index, monkeypatch):
    from src.generation import ollama

    def unexpected(*args, **kwargs):
        raise AssertionError("Ollama should not be called")

    monkeypatch.setattr(ollama.requests, "post", unexpected)
    monkeypatch.setenv("RAG_GENERATOR", "ollama")
    graph = create_agent_graph(search_and_index, calculator, create_generator())

    arithmetic = graph.invoke({"question": "What is 12 * 7?"})
    assert arithmetic["status"] == "answered"
    assert arithmetic["calculation_result"]["result"] == 84
    unanswered = graph.invoke({"question": "What is the xylophone troubleshooting protocol?"})
    assert unanswered["status"] == "abstained"


def test_streamlit_displays_fallback_and_selected_sources(search_and_index, monkeypatch):
    from src.generation import ollama

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(ollama.requests, "post", unavailable)
    monkeypatch.setenv("RAG_GENERATOR", "ollama")
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    app.chat_input[0].set_value("What does json.dumps do?").run(timeout=10)

    assert not app.exception
    result = app.session_state["messages"][-1]["result"]
    assert result["generation_backend"] == "dummy"
    assert result["generation_fallback_reason"]
    assert result["citations"]
    assert any("dummy" in item.value.lower() for item in app.caption)
    assert any("fallback" in item.value.lower() for item in app.warning)
