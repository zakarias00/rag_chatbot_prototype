from typing import TypedDict


"""Internal state shared by the RAG agent and its subgraphs."""
class AgentState(TypedDict, total=False):
    question: str
    subtasks: list[str]
    search_query: str
    documentation_question: str | None
    documents: list[dict]
    calculation_request: dict | None
    calculation_result: dict | None
    retry_count: int
    evidence_sufficient: bool
    search_error: str | None
    status: str
    answer: str
    citations: list[dict]
    trace: list[dict]
    generation_backend: str | None
    generation_fallback_reason: str | None
