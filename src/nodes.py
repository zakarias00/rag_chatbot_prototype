from __future__ import annotations

import math
import re
from typing import Any

from numpy import minimum

from src.generation.base import AnswerGenerator
from src.rag.querying import evidence_facets
from src.state import AgentState

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
EXPRESSION = re.compile(rf"(?<![\w.])({NUMBER})\s*([+*×/\-])\s*({NUMBER})(?![\w.])")
MATH_HINT = re.compile(r"\b(?:calculate|compute|multiply|multiplied|divide|divided|subtract|add|plus|minus|times)\b|(?<=\d)\s*[+*/×-]", re.I)
PER_DAY = re.compile(rf"({NUMBER})\s*(KB|MB|GB)\s+per\s+day\b.*?\b(?:for|after|over|in)\s+({NUMBER})\s+days?\b", re.I)
WORDS_OP = re.compile(rf"\b(multiply|divide|add|subtract)\s+({NUMBER})\s+(by|and|from)\s+({NUMBER})\b", re.I)
DOC_HINT = re.compile(r"\b(?:python|documentation|docs?|json|pathlib|venv|csv|logging|exception|exceptions|traceback|log|logs|virtual|module|function|method)\b", re.I)
DOC_REQUEST = re.compile(r"\b(?:how\s+(?:can|do|does|to)|what\s+(?:is|does|are)|explain|describe|documentation|configure|using|write\s+logs?)\b", re.I)
TOKEN = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", re.I)
STOP = frozenset("a also an and are as at be by calculate can could describe difference do does explain for from how i in is it me my of on or please show tell that the their this to use what when where which why with work would you your python documentation docs doc about question using between information".split())



def _event(state: AgentState, node: str, message: str) -> list[dict]:
    return [*state.get("trace", []), {"node": node, "message": message}]


def _number(value: str) -> int | float:
    if "." not in value:
        return int(value)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Number must be finite")
    return int(number) if number.is_integer() else number


def _parse_calculation(question: str) -> tuple[dict | None, tuple[int, int] | None]:
    """Extract one supported binary calculation; never evaluate user code."""
    match = PER_DAY.search(question)
    if match:
        return {"operation": "multiply", "operands": [_number(match[1]), _number(match[3])], "unit": match[2].upper()}, match.span()
    match = WORDS_OP.search(question)
    if match:
        op, left, preposition, right = match.groups()
        op, preposition = op.lower(), preposition.lower()
        allowed = {"multiply": "by", "divide": "by", "add": "and", "subtract": "from"}
        if preposition != allowed[op]:
            return None, None
        operands = [_number(left), _number(right)]
        if op == "subtract":
            operands.reverse()
        return {"operation": op, "operands": operands}, match.span()
    match = EXPRESSION.search(question)
    if match:
        operation = {"+": "add", "-": "subtract", "*": "multiply", "×": "multiply", "/": "divide"}[match[2]]
        return {"operation": operation, "operands": [_number(match[1]), _number(match[3])]}, match.span()
    return None, None


def _terms(text: str) -> set[str]:
    return {token.lower() for token in TOKEN.findall(text) if token.lower() not in STOP and len(token) > 1}

_UNSUPPORTED = re.compile(
    r"\b(?:my|our)\s+(?:company|organisation|organization)(?:\'s)?\b"
    r"|\b(?:current|latest|today\'s)\s+(?:price|pricing|rate\s+limit)\b"
    r"|\b(?:api\s+rate\s+limit|cloud\s+service\s+price)\b"
    r"|\b(?:my|our)\s+virtual\s+environment\b.*\b(?:currently|right\s+now)\b",
    re.I,
)


def _matches_facet(facet: str, document: dict) -> bool:
    """A lexical relevance heuristic, not a factual entailment classifier."""
    text = " ".join(str(document.get(key, "")) for key in ("title", "section", "text"))
    text = re.sub(r"\\([_*])", r"\1", text)
    normalized = text.lower().replace("_", " ").replace(".", " ")
    symbols = re.findall(r"(?<![\w.])([A-Za-z_]\w*\.[A-Za-z_]\w*)(?![\w.])", facet)
    if symbols:
        if not all(re.search(rf"(?<![\w.]){re.escape(name)}(?![\w.])", text, re.I) for name in symbols):
            return False
    module = re.search(r"\b(?:with|using|via)\s+(pathlib|json|venv|csv|logging)\b(?!\.)", facet, re.I)
    if module and document.get("document_id", "").lower() != module.group(1).lower():
        return False
    terms = _terms(facet)
    if not terms:
        return False
    matched = sum(
        bool(re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text, re.I))
        or ("." not in term and bool(re.search(rf"\b{re.escape(term)}\b", normalized)))
        for term in terms
    )
    minimum = 1 if len(terms) <= 2 else 2
    return (
        matched >= minimum
        and matched / len(terms) >= 0.40
    )


def _supported_documents(query: str, documents: list[dict]) -> list[dict]:
    """Keep chunks relevant to at least one independently answerable facet."""
    if _UNSUPPORTED.search(query):
        return []
    facets = evidence_facets(query)
    return [document for document in documents
            if any(_matches_facet(facet, document) for facet in facets)]


def _covered_facets(query: str, documents: list[dict]) -> tuple[int, int]:
    facets = evidence_facets(query)
    return (
        sum(any(_matches_facet(facet, doc) for doc in documents) for facet in facets),
        len(facets),
    )


def create_nodes(search_tool: Any, calculator_tool: Any, generator: AnswerGenerator) -> dict[str, Any]:
    def plan(state: AgentState) -> dict:
        question = state.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a nonempty string")
        try:
            calculation, span = _parse_calculation(question)
        except (ValueError, OverflowError):
            calculation, span = None, None
        if calculation:
            remaining = question[:span[0]] + " " + question[span[1]:]
            if re.search(r"\d", remaining) or re.search(r"[+*/×-]", remaining):
                calculation = None

        if calculation:
            needs_docs = bool(DOC_HINT.search(remaining))
            if PER_DAY.search(question):
                needs_docs = needs_docs and bool(DOC_REQUEST.search(remaining))
            tasks = (["search_documentation"] if needs_docs else []) + ["calculate"]
        elif MATH_HINT.search(question) or PER_DAY.search(question) or span:
            return {"subtasks": [], "calculation_request": None, "calculation_result": None, "documents": [], "citations": [], "generation_backend": None, "generation_fallback_reason": None, "search_query": question, "retry_count": 0, "evidence_sufficient": False, "status": "clarification", "answer": "Please provide one complete calculation with two numbers and an operation, for example 12 * 7.", "trace": _event(state, "plan", "Calculation input is incomplete or unsupported.")}
        else:
            tasks = ["search_documentation"]
        if calculation and "search_documentation" in tasks:
            remaining = re.sub(r"\b(?:and\s+what\s+is|and\s+calculate)\s*\??\s*$", "", remaining, flags=re.I).strip()
        search_query = remaining if calculation and "search_documentation" in tasks else question
        return {"subtasks": tasks, "calculation_request": calculation, "calculation_result": None, "documents": [], "citations": [], "generation_backend": None, "generation_fallback_reason": None, "search_query": search_query, "documentation_question": search_query if "search_documentation" in tasks else None, "retry_count": 0, "evidence_sufficient": False, "search_error": None, "status": "planned", "answer": "", "trace": _event(state, "plan", "Planned: " + ", ".join(tasks))}

    def route_plan(state: AgentState) -> str:
        if state["status"] == "clarification":
            return "finalize"
        return "retrieve" if "search_documentation" in state["subtasks"] else "calculate"

    def retrieve(state: AgentState) -> dict:
        try:
            result = search_tool.invoke({"query": state["search_query"]})
            documents = result["documents"]
        except OSError as exc:
            error_type = type(exc).__name__
            return {"documents": [], "search_error": error_type, "trace": _event(state, "retrieve", f"Search failed ({error_type}).")}
        return {"documents": documents, "search_error": None, "trace": _event(state, "retrieve", f"Retrieved {len(documents)} candidate chunks.")}

    def assess_evidence(state: AgentState) -> dict:
        query = state.get("documentation_question") or state["search_query"]
        documents = _supported_documents(query, state["documents"])
        covered, needed = _covered_facets(query, documents)
        sufficient = covered == needed and bool(documents)
        return {"documents": documents, "evidence_sufficient": sufficient,
                "trace": _event(state, "assess_evidence",
                                f"{covered}/{needed} question facets supported by {len(documents)} chunks (heuristic).") }

    def route_evidence(state: AgentState) -> str:
        if not state["evidence_sufficient"]:
            if state["retry_count"] < 1:
                return "refine_query"
            return "calculate" if "calculate" in state["subtasks"] else "abstain"
        return "calculate" if "calculate" in state["subtasks"] else "generate_answer"

    def refine_query(state: AgentState) -> dict:
        terms = [word for word in TOKEN.findall(state["search_query"]) if word.lower() not in STOP]
        refined = " ".join(terms) or state["question"]
        return {"search_query": refined, "retry_count": state["retry_count"] + 1, "trace": _event(state, "refine_query", "Refined the search query for one retry.")}

    def calculate(state: AgentState) -> dict:
        request = state["calculation_request"]
        try:
            result = calculator_tool.invoke({"operation": request["operation"], "operands": request["operands"]})
        except ValueError as exc:
            return {"status": "clarification", "answer": f"The calculation could not be completed: {exc}", "trace": _event(state, "calculate", "Calculation input could not be evaluated.")}
        return {"calculation_result": result, "trace": _event(state, "calculate", "Calculator completed the requested operation.")}

    def route_calculation(state: AgentState) -> str:
        return "finalize" if state["status"] == "clarification" else "generate_answer"

    def generate_answer(state: AgentState) -> dict:
        documents = state.get("documents", []) if state.get("evidence_sufficient", True) else []
        citations = []
        parts = []
        fallback_reason = None
        backend = "calculator"
        if documents:
            result = generator.generate(state.get("documentation_question") or state["question"], documents)
            backend, fallback_reason = result.backend, result.fallback_reason
            parts.append(result.text)
            if backend == "ollama":
                cited_numbers = sorted({int(match) for match in re.findall(r"(?<![\w])\[(\d+)\]", result.text)})
                if not cited_numbers or any(number < 1 or number > len(documents) for number in cited_numbers):
                    raise ValueError("The generator returned invalid source references")
            else:
                cited_numbers = list(range(1, len(documents) + 1))
            citations = [
                {"number": number, **{key: documents[number - 1].get(key)
                 for key in ("chunk_id", "title", "section", "source_url")}}
                for number in cited_numbers
            ]
            if backend == "ollama":
                sources = [f"[{item['number']}] {item.get('source_url', '')}" for item in citations]
                parts.append("Sources:\n" + "\n".join(sources))
        if state.get("calculation_result") is not None:
            calculation = state["calculation_result"]
            unit = state["calculation_request"].get("unit", "")
            parts.append(f"Calculation ({calculation['operation']}): {calculation['result']}" + (f" {unit}" if unit else ""))
        message = f"Prepared an answer using {backend}."
        if fallback_reason:
            message += f" Fallback: {fallback_reason}"
        missing_docs = "search_documentation" in state["subtasks"] and not state.get("evidence_sufficient", False)
        if missing_docs:
            parts.insert(0, "The documentation part could not be verified from the available sources.")
        return {"answer": "\n\n".join(parts), "citations": citations,
                "status": "partial" if missing_docs else "answered",
                "generation_backend": backend, "generation_fallback_reason": fallback_reason,
                "trace": _event(state, "generate_answer", message)}

    def abstain(state: AgentState) -> dict:
        answer = "The documentation search failed after a retry. Please check the index and try again." if state.get("search_error") else "I could not find sufficient supporting evidence in the available Python documentation."
        return {"answer": answer, "citations": [], "status": "abstained", "trace": _event(state, "abstain", "No usable evidence after the bounded retry.")}

    def finalize(state: AgentState) -> dict:
        valid = {doc.get("chunk_id") for doc in state.get("documents", [])}
        if any(c.get("chunk_id") not in valid for c in state.get("citations", [])):
            raise ValueError("A citation does not refer to retrieved evidence")
        return {"trace": _event(state, "finalize", "Completed the workflow.")}

    return {
        "plan": plan, "route_plan": route_plan, "retrieve": retrieve,
        "assess_evidence": assess_evidence, "route_evidence": route_evidence,
        "refine_query": refine_query, "calculate": calculate,
        "route_calculation": route_calculation, "generate_answer": generate_answer,
        "abstain": abstain, "finalize": finalize,
    }
