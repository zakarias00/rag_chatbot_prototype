import pytest

from src.graph import create_agent_graph
from src.rag.index import DocumentationIndex, build_index
from src.rag.ingestion import PROJECT_ROOT, ingest
from src.rag.subgraph import create_rag_subgraph
from src.tools.calculator import calculator
from src.tools.search import create_search_documentation_tool


class RecordingTool:
    """Record real tool calls without changing their behavior."""

    def __init__(self, tool):
        self.tool = tool
        self.calls = []

    def invoke(self, arguments):
        self.calls.append(arguments.copy())
        return self.tool.invoke(arguments)


class EmptySearch:
    def __init__(self):
        self.calls = []

    def invoke(self, arguments):
        self.calls.append(arguments.copy())
        return {"query": arguments["query"], "documents": []}


@pytest.fixture
def tools_and_graph(tmp_path):
    chunks_path = tmp_path / "chunks.jsonl"
    index_dir = tmp_path / "index"
    ingest(PROJECT_ROOT / "data/sources.json", chunks_path)
    build_index(chunks_path, index_dir)
    index = DocumentationIndex(chunks_path, index_dir)
    rag = create_rag_subgraph(index, k=5)
    search = RecordingTool(create_search_documentation_tool(rag))
    calc = RecordingTool(calculator)
    return search, calc, create_agent_graph(search, calc)


def nodes(result):
    return [event["node"] for event in result["trace"]]


def test_documentation_question_uses_real_retrieval_with_sources(tools_and_graph):
    search, calc, graph = tools_and_graph
    result = graph.invoke({"question": "What does json.dumps do?"})

    assert result["status"] == "answered"
    assert len(search.calls) >= 1
    assert calc.calls == []
    assert any(doc["document_id"] == "json" for doc in result["documents"])
    assert result["citations"]
    retrieved_ids = {doc["chunk_id"] for doc in result["documents"]}
    assert all(citation["chunk_id"] in retrieved_ids for citation in result["citations"])
    assert any("json.html" in citation["source_url"] for citation in result["citations"])
    assert "json.dumps" in result["answer"]
    assert {"plan", "retrieve", "assess_evidence", "generate_answer", "finalize"} <= set(nodes(result))


def test_calculation_only_skips_retrieval(tools_and_graph):
    search, calc, graph = tools_and_graph
    result = graph.invoke({"question": "What is 12 * 7?"})

    assert result["status"] == "answered"
    assert search.calls == []
    assert len(calc.calls) == 1
    assert calc.calls[0]["operation"] == "multiply"
    assert calc.calls[0]["operands"] == [12, 7]
    assert result["calculation_result"]["result"] == 84
    assert "84" in result["answer"]
    assert not result["citations"]
    assert "calculate" in nodes(result)


def test_combined_question_executes_both_tools(tools_and_graph):
    search, calc, graph = tools_and_graph
    result = graph.invoke({"question": "What does json.dumps do and what is 12 * 7?"})

    assert result["status"] == "answered"
    assert search.calls and len(calc.calls) == 1
    assert result["calculation_result"]["result"] == 84
    assert "84" in result["answer"]
    assert "json.dumps" in result["answer"]
    assert result["citations"]
    assert {"retrieve", "calculate"} <= set(nodes(result))


def test_missing_calculation_input_asks_for_clarification(tools_and_graph):
    search, calc, graph = tools_and_graph
    result = graph.invoke({"question": "What is 12 * ?"})

    assert result["status"] == "clarification"
    assert result["answer"].strip()
    assert search.calls == []
    assert calc.calls == []


def test_unsupported_question_abstains_with_real_corpus(tools_and_graph):
    search, calc, graph = tools_and_graph
    result = graph.invoke({"question": "What is my company retention policy?"})

    assert result["status"] == "abstained"
    assert result["answer"].strip()
    assert not result["citations"]
    assert calc.calls == []
    assert len(search.calls) <= 2


@pytest.mark.parametrize("question", [
    "What is the retention period for Python logging in my company?",
    "What is my company's logging retention policy?",
    "What is current price of a Python logging cloud service?",
    "What is the JSON API rate limit?",
])
def test_unsupported_specific_questions_do_not_answer_on_topic_words_alone(tools_and_graph, question):
    _, _, graph = tools_and_graph
    result = graph.invoke({"question": question})
    assert result["status"] == "abstained"
    assert not result["citations"]


@pytest.mark.parametrize("question", ["What is 2 + 3 * 4?", "calculate 2 + 3 * 4"])
def test_multi_operation_expression_is_not_partially_calculated(tools_and_graph, question):
    _, calc, graph = tools_and_graph
    result = graph.invoke({"question": question})
    assert result["status"] == "clarification"
    assert calc.calls == []


def test_large_integer_calculation_remains_exact(tools_and_graph):
    _, calc, graph = tools_and_graph
    result = graph.invoke({"question": "What is 9007199254740993 + 1?"})
    assert result["status"] == "answered"
    assert calc.calls[0]["operands"] == [9007199254740993, 1]
    assert result["calculation_result"]["result"] == 9007199254740994


@pytest.mark.parametrize("question", [
    "A file grows by 12 MB per day for 7 days. How much growth?",
    "A log file grows by 12 MB per day for 7 days. How much growth?",
])
def test_per_day_rate_calculation_does_not_search_documentation(tools_and_graph, question):
    search, calc, graph = tools_and_graph
    result = graph.invoke({"question": question})
    assert result["status"] == "answered"
    assert search.calls == []
    assert calc.calls[0]["operands"] == [12, 7]
    assert result["calculation_result"]["result"] == 84
    assert "MB" in result["answer"]


def test_pathlib_read_question_returns_reading_evidence(tools_and_graph):
    _, _, graph = tools_and_graph
    result = graph.invoke({"question": "How do I read a text file using pathlib?"})
    assert result["status"] == "answered"
    assert result["documents"][0]["section"] == "Reading and writing files"


def test_failed_retrieval_retries_once_then_terminates():
    search = EmptySearch()
    calc = RecordingTool(calculator)
    graph = create_agent_graph(search, calc)
    result = graph.invoke({"question": "What is the xylophone troubleshooting protocol?"})

    assert result["status"] == "abstained"
    assert result["retry_count"] == 1
    assert len(search.calls) == 2
    assert nodes(result).count("refine_query") == 1
    assert calc.calls == []
    assert not result["citations"]


def test_repeated_search_failure_retries_once_and_reports_error():
    class FailingSearch:
        def __init__(self):
            self.calls = 0

        def invoke(self, arguments):
            self.calls += 1
            raise OSError("index unavailable")

    search = FailingSearch()
    result = create_agent_graph(search, calculator).invoke({"question": "What does json.dumps do?"})

    assert result["status"] == "abstained"
    assert result["retry_count"] == 1
    assert search.calls == 2
    assert result["search_error"] == "OSError"
    assert "search failed" in result["answer"].lower()
    assert not result["citations"]


def test_transient_search_failure_recovers_and_clears_error(tools_and_graph):
    search, calc, _ = tools_and_graph

    class TransientSearch:
        def __init__(self):
            self.calls = 0

        def invoke(self, arguments):
            self.calls += 1
            if self.calls == 1:
                raise OSError("temporary problem")
            return search.invoke(arguments)

    transient = TransientSearch()
    result = create_agent_graph(transient, calc).invoke({"question": "What does json.dumps do?"})

    assert result["status"] == "answered"
    assert result["retry_count"] == 1
    assert transient.calls == 2
    assert result["search_error"] is None
    assert result["citations"]

@pytest.mark.parametrize("question", [
    "What happens to existing content when "
    "Path.write_text writes to a file?",

    "Does json ensure_ascii change how "
    "non-ASCII characters are represented?",

    "When does logging.basicConfig leave "
    "the root logger unchanged, and how "
    "does force affect this?",
])
def test_supported_documentation_questions(
    tools_and_graph, question
):
    _, _, graph = tools_and_graph

    result = graph.invoke({"question": question})

    assert result["status"] == "answered"
    assert result["documents"]
    assert result["citations"]

def test_cannot_inspect_users_live_environment(
    tools_and_graph
):
    _, _, graph = tools_and_graph

    result = graph.invoke({
        "question": (
            "Which packages are installed in my "
            "virtual environment right now?"
        )
    })

    assert result["status"] == "abstained"
    assert result["citations"] == []

def test_combined_request_does_not_skip_calculator(
    tools_and_graph
):
    _, calc, graph = tools_and_graph

    result = graph.invoke({
        "question": (
            "What does json.loads accept "
            "and what is 9 + 6?"
        )
    })

    assert len(calc.calls) == 1
    assert result["calculation_result"]["result"] == 15
    assert result["status"] in {"answered", "partial"}