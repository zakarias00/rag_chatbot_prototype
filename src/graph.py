from __future__ import annotations

import argparse
import json
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.generation.base import AnswerGenerator
from src.generation.dummy import DummyGenerator
from src.nodes import create_nodes
from src.state import AgentState


def create_agent_graph(search_tool: Any, calculator_tool: Any, generator: AnswerGenerator | None = None):
    """Compile the graph; the deterministic dummy generator is the default."""
    nodes = create_nodes(search_tool, calculator_tool, generator if generator is not None else DummyGenerator())
    builder = StateGraph(AgentState)
    for name in ("plan", "retrieve", "assess_evidence", "refine_query", "calculate", "generate_answer", "abstain", "finalize"):
        builder.add_node(name, nodes[name])
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", nodes["route_plan"], {"retrieve": "retrieve", "calculate": "calculate", "finalize": "finalize"})
    builder.add_edge("retrieve", "assess_evidence")
    builder.add_conditional_edges("assess_evidence", nodes["route_evidence"], {"refine_query": "refine_query", "abstain": "abstain", "calculate": "calculate", "generate_answer": "generate_answer"})
    builder.add_edge("refine_query", "retrieve")
    builder.add_conditional_edges("calculate", nodes["route_calculation"], {"finalize": "finalize", "generate_answer": "generate_answer"})
    builder.add_edge("generate_answer", "finalize")
    builder.add_edge("abstain", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()


def main() -> None:
    from src.config import create_generator
    from src.rag.index import DocumentationIndex
    from src.rag.subgraph import create_rag_subgraph
    from src.tools.calculator import calculator
    from src.tools.search import create_search_documentation_tool

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Documentation or simple arithmetic question")
    args = parser.parse_args()
    search_tool = create_search_documentation_tool(create_rag_subgraph(DocumentationIndex()))
    result = create_agent_graph(search_tool, calculator, generator=create_generator()).invoke({"question": args.question})
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
