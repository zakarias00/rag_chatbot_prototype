import json

import pytest

from src.rag.index import DocumentationIndex, build_index
from src.rag.ingestion import ingest
from src.rag.subgraph import create_rag_subgraph
from src.tools.search import create_search_documentation_tool


class RecordingIndex:
    """A controllable index that records calls made by the real graph."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, k=5):
        self.calls.append((query, k))
        return self.results


@pytest.fixture
def indexed_documents(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "json.md").write_text(
        "# JSON\n\n## json.dump and json.dumps\n\n"
        "json.dump writes to a file, while json.dumps returns a string.\n\n"
        "## Reading JSON\n\njson.load reads a JSON file.\n",
        encoding="utf-8",
    )
    manifest = [{
        "id": "json",
        "path": "data/raw/json.md",
        "title": "JSON reference",
        "source_url": "https://docs.python.org/3.12/library/json.html",
        "source_revision": "https://example.org/v3.12.8/json.rst",
        "python_version": "3.12.8",
        "retrieved_at": "2026-11-04",
        "license": "test license",
    }]
    manifest_file = tmp_path / "data" / "sources.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    chunks = tmp_path / "chunks.jsonl"
    ingest(manifest_file, chunks, project_root=tmp_path)
    index_dir = tmp_path / "index"
    build_index(chunks, index_dir)
    return DocumentationIndex(chunks, index_dir)


def test_graph_retrieves_real_index_and_preserves_sources(indexed_documents):
    graph = create_rag_subgraph(indexed_documents, k=2)
    result = graph.invoke({"query": "What is the difference between json.dump and json.dumps?"})

    assert result["search_query"]
    assert result["documents"]
    first = result["documents"][0]
    assert first["section"] == "json.dump and json.dumps"
    assert first["chunk_id"].startswith("json--")
    assert first["source_url"] == "https://docs.python.org/3.12/library/json.html"
    assert first["source_revision"].endswith("/json.rst")
    assert first["python_version"] == "3.12.8"
    assert first["score"] > 0
    assert graph.invoke({"query": "zzqxunmatchedword"})["documents"] == []


def test_graph_output_hides_intermediate_candidates_but_stream_exposes_them(indexed_documents):
    graph = create_rag_subgraph(indexed_documents, k=2)
    graph_input = {"query": "What does json.dumps do?"}

    result = graph.invoke(graph_input)
    assert result["documents"]
    assert "candidates" not in result

    updates = list(graph.stream(graph_input, stream_mode="updates"))
    retrieval = next(event["retrieve_chunks"] for event in updates if "retrieve_chunks" in event)
    assert retrieval["candidates"]
    assert retrieval["candidates"][0]["chunk_id"] == result["documents"][0]["chunk_id"]


def test_evidence_filter_deduplicates_and_respects_threshold():
    docs = [
        {"chunk_id": "a", "text": "first", "score": 0.9},
        {"chunk_id": "a", "text": "duplicate", "score": 0.8},
        {"chunk_id": "b", "text": "borderline", "score": 0.5},
        {"chunk_id": "c", "text": "weak", "score": 0.49},
        {"chunk_id": "d", "text": "zero", "score": 0.0},
    ]
    index = RecordingIndex(docs)
    graph = create_rag_subgraph(index, k=5, min_score=0.5)

    result = graph.invoke({"query": "  python documentation  "})

    assert index.calls == [(result["search_query"], 15)]
    assert [doc["chunk_id"] for doc in result["documents"]] == ["a", "b"]
    assert result["documents"][0]["text"] == "first"


def test_graph_rejects_blank_query_without_searching():
    index = RecordingIndex([])
    graph = create_rag_subgraph(index)

    with pytest.raises(ValueError):
        graph.invoke({"query": " \n\t "})
    assert index.calls == []


def test_tool_calls_graph_and_reuses_supplied_index():
    evidence = [{
        "chunk_id": "json-1",
        "text": "JSON evidence",
        "source_url": "https://example.org/json",
        "score": 0.8,
    }]
    index = RecordingIndex(evidence)
    tool = create_search_documentation_tool(create_rag_subgraph(index, k=3))

    assert tool.name == "search_documentation"
    first = tool.invoke({"query": "json.dump"})
    second = tool.invoke({"query": "json.loads"})

    assert len(first["documents"]) == 1

    for key, value in evidence[0].items():
        assert first["documents"][0][key] == value

    assert first["documents"][0]["search_facets"] == [0]
    assert isinstance(
        first["documents"][0]["ranking_score"], float
    )
    assert first["query"] == "json.dump"
    assert second["query"] == "json.loads"
    assert index.calls == [(first["search_query"], 15), (second["search_query"], 15)]


def test_cli_shows_final_documents_once_and_can_include_candidates(
    indexed_documents, monkeypatch, capsys
):
    import sys

    from src.rag import subgraph

    monkeypatch.setattr(subgraph, "DocumentationIndex", lambda *args: indexed_documents)
    query = "What does json.dumps do?"

    monkeypatch.setattr(sys, "argv", ["subgraph", query])
    subgraph.main()
    result = json.loads(capsys.readouterr().out)
    assert result["query"] == query
    assert result["documents"]
    assert "candidates" not in result
    ids = [item["chunk_id"] for item in result["documents"]]
    assert len(ids) == len(set(ids))

    monkeypatch.setattr(sys, "argv", ["subgraph", query, "--include-candidates"])
    subgraph.main()
    debug_result = json.loads(capsys.readouterr().out)
    assert debug_result["documents"] == result["documents"]
    assert debug_result["candidates"]