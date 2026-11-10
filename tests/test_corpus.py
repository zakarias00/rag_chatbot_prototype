import json

import pytest

from src.rag.index import DocumentationIndex, build_index
from src.rag.ingestion import ingest
from src.rag.subgraph import create_rag_subgraph


@pytest.fixture
def corpus(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "json.md").write_text(
        "# JSON documentation\n\n"
        "## json.dump and json.dumps\n\n"
        "The json.dump function writes JSON to a file. "
        "The json.dumps function returns a string.\n\n"
        "## Reading JSON\n\n"
        "The json.load function reads a JSON document from a file.\n",
        encoding="utf-8",
    )
    (raw / "venv.md").write_text(
        "# Virtual environments\n\n"
        "## Create a virtual environment\n\n"
        "Run python -m venv to create an isolated environment.\n",
        encoding="utf-8",
    )
    manifest = [
        {
            "id": source,
            "path": f"data/raw/{source}.md",
            "title": f"{source} reference",
            "source_url": f"https://docs.python.org/3.12/library/{source}.html",
            "source_revision": f"https://example.org/v3.12.8/{source}.rst",
            "python_version": "3.12.8",
            "retrieved_at": "2026-11-04",
            "license": "test license",
        }
        for source in ("json", "venv")
    ]
    manifest_path = tmp_path / "data" / "sources.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    chunks = tmp_path / "data" / "processed" / "chunks.jsonl"
    return tmp_path, manifest_path, chunks


def test_ingestion_is_reproducible_and_retains_source_metadata(corpus):
    root, manifest, chunks = corpus
    assert ingest(manifest, chunks, project_root=root) == 3
    first = chunks.read_bytes()
    records = [json.loads(line) for line in first.splitlines()]
    assert len({record["chunk_id"] for record in records}) == len(records)
    assert records[0]["section"] == "json.dump and json.dumps"
    assert records[0]["source_path"] == "data/raw/json.md"
    assert records[0]["source_url"].endswith("/json.html")
    assert records[0]["source_revision"].endswith("/json.rst")
    assert records[0]["python_version"] == "3.12.8"
    assert ingest(manifest, chunks, project_root=root) == 3
    assert chunks.read_bytes() == first


def test_search_returns_relevant_section_and_attribution(corpus):
    root, manifest, chunks = corpus
    ingest(manifest, chunks, project_root=root)
    index_dir = root / "index"
    assert build_index(chunks, index_dir) == 3
    index = DocumentationIndex(chunks, index_dir)
    result = index.search("difference between json.dump and json.dumps", k=2)
    assert result[0]["section"] == "json.dump and json.dumps"
    assert result[0]["document_id"] == "json"
    assert result[0]["source_url"].endswith("/json.html")
    assert result[0]["score"] > 0
    assert index.search("qzxwvunmatchedterm", k=2) == []


def test_stale_index_is_rejected(corpus):
    root, manifest, chunks = corpus
    ingest(manifest, chunks, project_root=root)
    index_dir = root / "index"
    build_index(chunks, index_dir)
    with chunks.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="(?i)(changed|stale|rebuild)"):
        DocumentationIndex(chunks, index_dir)


def test_ingestion_rejects_paths_outside_project(corpus):
    root, manifest, chunks = corpus
    records = json.loads(manifest.read_text(encoding="utf-8"))
    records[0]["path"] = "../outside.md"
    manifest.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)(path|outside|root)"):
        ingest(manifest, chunks, project_root=root)


def test_repeated_ingestion_and_index_build_do_not_duplicate_graph_results(corpus):
    root, manifest, chunks = corpus
    index_dir = root / "index"
    query = "difference between json.dump and json.dumps"

    def run_pipeline():
        count = ingest(manifest, chunks, project_root=root)
        assert build_index(chunks, index_dir) == count
        graph = create_rag_subgraph(DocumentationIndex(chunks, index_dir), k=5)
        return count, graph.invoke({"query": query})["documents"]

    first_count, first_results = run_pipeline()
    second_count, second_results = run_pipeline()
    ids = [item["chunk_id"] for item in second_results]

    assert first_count == second_count == 3
    assert first_results == second_results
    assert ids
    assert len(ids) == len(set(ids))
