"""Nodes for the main agent: plan, retrieve, check evidence, calculate, answer."""
from __future__ import annotations

import re
from typing import Any

from src.generation.base import AnswerGenerator
from src.rag.evidence import STOP, TOKEN, filter_evidence
from src.math_parser import PER_DAY, parse_calculation
from src.state import AgentState

MATH_HINT = re.compile(r"\b(?:calculate|compute|multiply|multiplied|divide|divided|subtract|add|plus|minus|times)\b|(?<=\d)\s*[+*/×-]", re.I)
DOC_HINT = re.compile(r"\b(?:python|documentation|docs?|json|pathlib|venv|csv|logging|exception|exceptions|traceback|log|logs|virtual|module|function|method)\b", re.I)
DOC_REQUEST = re.compile(r"\b(?:how\s+(?:can|do|does|to)|what\s+(?:is|does|are)|explain|describe|documentation|configure|using|write\s+logs?)\b", re.I)


def event(state: AgentState, node: str, message: str) -> list[dict]:
    return [*state.get("trace", []), {"node": node, "message": message}]


def make_citations(answer: str, documents: list[dict], backend: str) -> list[dict]:
    """Map numbered references in the generated answer back to retrieved chunks."""
    numbers = list(range(1, len(documents) + 1))
    if backend == "ollama":
        numbers = sorted({int(n) for n in re.findall(r"(?<![\w])\[(\d+)\]", answer)})
        if not numbers or any(n < 1 or n > len(documents) for n in numbers):
            raise ValueError("The generator returned invalid source references")
    keys = ("chunk_id", "title", "section", "source_url")
    return [{"number": n, **{key: documents[n - 1].get(key) for key in keys}} for n in numbers]


def create_nodes(search_tool: Any, calculator_tool: Any, generator: AnswerGenerator) -> dict[str, Any]:
    """Return the nodes and routing functions used by src.graph."""

    def plan(state: AgentState) -> dict:
        question = state.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a nonempty string")
        try:
            calculation, span = parse_calculation(question)
        except (ValueError, OverflowError):
            calculation, span = None, None

        remaining = question
        if calculation:
            remaining = (question[:span[0]] + " " + question[span[1]:]).strip()
            # Avoid treating a multi-step expression as a single calculation.
            if re.search(r"\d|[+*/×-]", remaining):
                calculation = None

        initial = {
            "calculation_request": calculation, "calculation_result": None,
            "documents": [], "citations": [], "generation_backend": None,
            "generation_fallback_reason": None, "retry_count": 0,
            "evidence_sufficient": False, "search_error": None,
        }
        if calculation:
            needs_docs = bool(DOC_HINT.search(remaining))
            if PER_DAY.search(question):
                needs_docs = needs_docs and bool(DOC_REQUEST.search(remaining))
            tasks = (["search_documentation"] if needs_docs else []) + ["calculate"]
        elif MATH_HINT.search(question) or PER_DAY.search(question) or span:
            return {
                **initial, "subtasks": [], "search_query": question,
                "status": "clarification",
                "answer": "Please provide one complete calculation with two numbers and an operation, for example 12 * 7.",
                "trace": event(state, "plan", "Calculation input is incomplete or unsupported."),
            }
        else:
            tasks = ["search_documentation"]

        if calculation and "search_documentation" in tasks:
            remaining = re.sub(r"\b(?:and\s+what\s+is|and\s+calculate)\s*\??\s*$", "", remaining, flags=re.I).strip()
        docs_query = remaining if calculation and "search_documentation" in tasks else question
        return {
            **initial, "subtasks": tasks, "search_query": docs_query,
            "documentation_question": docs_query if "search_documentation" in tasks else None,
            "status": "planned", "answer": "",
            "trace": event(state, "plan", "Planned: " + ", ".join(tasks)),
        }

    def route_plan(state: AgentState) -> str:
        if state["status"] == "clarification":
            return "finalize"
        return "retrieve" if "search_documentation" in state["subtasks"] else "calculate"

    def retrieve(state: AgentState) -> dict:
        try:
            documents = search_tool.invoke({"query": state["search_query"]})["documents"]
        except OSError as exc:
            reason = type(exc).__name__
            return {"documents": [], "search_error": reason, "trace": event(state, "retrieve", f"Search failed ({reason}).")}
        return {"documents": documents, "search_error": None, "trace": event(state, "retrieve", f"Retrieved {len(documents)} candidate chunks.")}

    def assess_evidence(state: AgentState) -> dict:
        question = state.get("documentation_question") or state["search_query"]
        documents, covered, total = filter_evidence(question, state["documents"])
        return {
            "documents": documents, "evidence_sufficient": bool(documents) and covered == total,
            "trace": event(state, "assess_evidence", f"{covered}/{total} question facets supported by {len(documents)} chunks (heuristic)."),
        }

    def route_evidence(state: AgentState) -> str:
        if not state["evidence_sufficient"]:
            if state["retry_count"] < 1:
                return "refine_query"
            return "calculate" if "calculate" in state["subtasks"] else "abstain"
        return "calculate" if "calculate" in state["subtasks"] else "generate_answer"

    def refine_query(state: AgentState) -> dict:
        terms = [token for token in TOKEN.findall(state["search_query"]) if token.lower() not in STOP]
        return {
            "search_query": " ".join(terms) or state["question"],
            "retry_count": state["retry_count"] + 1,
            "trace": event(state, "refine_query", "Refined the search query for one retry."),
        }

    def calculate(state: AgentState) -> dict:
        request = state["calculation_request"]
        try:
            result = calculator_tool.invoke({"operation": request["operation"], "operands": request["operands"]})
        except ValueError as exc:
            return {
                "status": "clarification", "answer": f"The calculation could not be completed: {exc}",
                "trace": event(state, "calculate", "Calculation input could not be evaluated."),
            }
        return {"calculation_result": result, "trace": event(state, "calculate", "Calculator completed the requested operation.")}

    def route_calculation(state: AgentState) -> str:
        return "finalize" if state["status"] == "clarification" else "generate_answer"

    def generate_answer(state: AgentState) -> dict:
        documents = state.get("documents", []) if state.get("evidence_sufficient", True) else []
        parts = []
        citations = []
        backend, fallback_reason = "calculator", None

        if documents:
            response = generator.generate(state.get("documentation_question") or state["question"], documents)
            backend, fallback_reason = response.backend, response.fallback_reason
            parts.append(response.text)
            citations = make_citations(response.text, documents, backend)
            if backend == "ollama":
                parts.append("Sources:\n" + "\n".join(f"[{c['number']}] {c['source_url']}" for c in citations))

        if state.get("calculation_result") is not None:
            result = state["calculation_result"]
            unit = state["calculation_request"].get("unit", "")
            parts.append(f"Calculation ({result['operation']}): {result['result']}" + (f" {unit}" if unit else ""))

        missing_docs = "search_documentation" in state["subtasks"] and not state.get("evidence_sufficient", False)
        if missing_docs:
            parts.insert(0, "The documentation part could not be verified from the available sources.")
        message = f"Prepared an answer using {backend}."
        if fallback_reason:
            message += f" Fallback: {fallback_reason}"
        return {
            "answer": "\n\n".join(parts), "citations": citations,
            "status": "partial" if missing_docs else "answered",
            "generation_backend": backend, "generation_fallback_reason": fallback_reason,
            "trace": event(state, "generate_answer", message),
        }

    def abstain(state: AgentState) -> dict:
        if state.get("search_error"):
            answer = "The documentation search failed after a retry. Please check the index and try again."
        else:
            answer = "I could not find sufficient supporting evidence in the available Python documentation."
        return {"answer": answer, "citations": [], "status": "abstained", "trace": event(state, "abstain", "No usable evidence after the bounded retry.")}

    def finalize(state: AgentState) -> dict:
        known = {doc.get("chunk_id") for doc in state.get("documents", [])}
        if any(citation.get("chunk_id") not in known for citation in state.get("citations", [])):
            raise ValueError("A citation does not refer to retrieved evidence")
        return {"trace": event(state, "finalize", "Completed the workflow.")}

    return {
        "plan": plan, "route_plan": route_plan,
        "retrieve": retrieve, "assess_evidence": assess_evidence,
        "route_evidence": route_evidence, "refine_query": refine_query,
        "calculate": calculate, "route_calculation": route_calculation,
        "generate_answer": generate_answer, "abstain": abstain, "finalize": finalize,
    }
