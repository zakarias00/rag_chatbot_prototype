from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.rag.index import DEFAULT_CHUNKS, DEFAULT_INDEX, DocumentationIndex
from src.rag.querying import retrieve_diversified


class RagState(TypedDict, total=False):
    """Input, intermediate results and output shared by the retrieval nodes."""
    query: str
    search_query: str
    candidates: list[dict]
    documents: list[dict]


class RagOutput(TypedDict):
    """Public result; intermediate candidates remain in the graph state."""

    query: str
    search_query: str
    documents: list[dict]


def create_rag_subgraph(index: DocumentationIndex, *, k: int = 5, min_score: float = 0.0):
    """Compile a retrieval graph using an already loaded documentation index."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not math.isfinite(min_score) or not 0 <= min_score <= 1:
        raise ValueError("min_score must be a finite number between 0 and 1")

    def prepare_query(state: RagState) -> dict:
        query = state.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a nonempty string")
        # Retain punctuation in Python symbols such as json.dumps and Path.read_text.
        return {"search_query": " ".join(query.split())}

    def retrieve_chunks(state: RagState) -> dict:
        return {"candidates": retrieve_diversified(index, state["search_query"], k=k, pool=max(15, k))}

    def select_evidence(state: RagState) -> dict:
        selected, seen = [], set()
        for candidate in state["candidates"]:
            score = candidate["score"]
            chunk_id = candidate["chunk_id"]
            if score <= 0 or score < min_score or chunk_id in seen:
                continue
            seen.add(chunk_id)
            selected.append(candidate)
        return {"documents": selected}

    builder = StateGraph(RagState, output_schema=RagOutput)
    builder.add_node("prepare_query", prepare_query)
    builder.add_node("retrieve_chunks", retrieve_chunks)
    builder.add_node("select_evidence", select_evidence)
    builder.add_edge(START, "prepare_query")
    builder.add_edge("prepare_query", "retrieve_chunks")
    builder.add_edge("retrieve_chunks", "select_evidence")
    builder.add_edge("select_evidence", END)
    return builder.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Question or search query")
    parser.add_argument("--k", type=int, default=5, help="Maximum number of candidates")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum cosine similarity")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)
    parser.add_argument(
        "--include-candidates", action="store_true",
        help="Include intermediate candidates as well as selected documents",
    )
    args = parser.parse_args()
    index = DocumentationIndex(args.chunks, args.index_dir)
    graph = create_rag_subgraph(index, k=args.k, min_score=args.min_score)
    if args.include_candidates:
        # Node updates expose the intermediate candidates for diagnostics.
        output = {"query": args.query}
        for event in graph.stream({"query": args.query}, stream_mode="updates"):
            for update in event.values():
                output.update(update)
    else:
        output = graph.invoke({"query": args.query})
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
