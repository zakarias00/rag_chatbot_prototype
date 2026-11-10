from langchain_core.tools import tool


def create_search_documentation_tool(rag_graph):
    """Bind a reusable compiled RAG graph to a structured search tool."""

    @tool
    def search_documentation(query: str) -> dict:
        """Search the local Python documentation corpus for relevant evidence.

        Return matching chunks with source metadata and similarity scores.
        An empty documents list means no candidates met the configured cutoff.
        """
        state = rag_graph.invoke({"query": query})
        return {
            "query": state["query"],
            "search_query": state["search_query"],
            "documents": state["documents"],
        }

    return search_documentation
