from __future__ import annotations

import logging

import streamlit as st

from src.config import Settings, create_generator, load_settings
from src.graph import create_agent_graph
from src.rag.index import DEFAULT_CHUNKS, DEFAULT_INDEX, DocumentationIndex
from src.rag.subgraph import create_rag_subgraph
from src.tools.calculator import calculator
from src.tools.search import create_search_documentation_tool

logger = logging.getLogger(__name__)


def index_signature() -> tuple[tuple[int, int], ...]:
    """Detect index rebuilds so the next question loads the updated files."""
    files = (DEFAULT_CHUNKS, DEFAULT_INDEX / "metadata.json", DEFAULT_INDEX / "matrix.npz")
    return tuple((stat.st_mtime_ns, stat.st_size) for stat in (path.stat() for path in files))


@st.cache_resource(show_spinner=False)
def load_agent(signature: tuple[tuple[int, int], ...], settings: Settings):
    """Reuse the index and agent while their files and settings are unchanged."""
    index = DocumentationIndex(DEFAULT_CHUNKS, DEFAULT_INDEX)
    search = create_search_documentation_tool(create_rag_subgraph(index))
    return create_agent_graph(search, calculator, create_generator(settings))


def show_result(result: dict) -> None:
    """Show one answer and the supporting evidence and workflow events."""
    status = result.get("status")
    if status == "abstained":
        st.caption("No supported answer found")
    elif status == "partial":
        st.caption(
            "Partial answer: some parts could not be verified"
        )
    elif status == "clarification":
        st.caption("More information needed")
    st.markdown(result.get("answer", "No answer was returned."))
    backend = result.get("generation_backend")
    if backend:
        st.caption(f"Answer method: {backend}")
    fallback_reason = result.get("generation_fallback_reason")
    if fallback_reason:
        st.warning(f"Ollama was unavailable; using the extractive fallback. {fallback_reason}")

    with st.expander("Sources"):
        citations = result.get("citations", [])
        if citations:
            st.caption("Retrieved sources; verify generated claims against the excerpts.")
        if not citations:
            st.caption("No sources were used for this answer.")
        for number, citation in enumerate(citations, 1):
            title = citation.get("title") or "Documentation"
            section = citation.get("section") or "Section"
            url = citation.get("source_url")
            st.write(f"[{citation.get('number', number)}] {title} — {section}")
            if url:
                st.write(url)

    with st.expander("Retrieved evidence"):
        documents = result.get("documents", [])
        if not documents:
            st.caption("No supporting excerpts were selected.")
        for number, document in enumerate(documents, 1):
            title = document.get("title") or "Documentation"
            section = document.get("section") or "Section"
            st.write(f"[{number}] {title} — {section}")
            st.text(document.get("text", ""))
            score = document.get("score")
            if isinstance(score, (int, float)):
                st.caption(f"Retrieval similarity: {score:.3f}")

    with st.expander("Workflow trace"):
        events = result.get("trace", [])
        if not events:
            st.caption("No workflow events were recorded.")
        for number, event in enumerate(events, 1):
            st.write(f"{number}. {event.get('node', 'step')}: {event.get('message', '')}")


def show_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        elif "error" in message:
            st.error(message["error"])
            if message.get("setup_required"):
                st.code("python -m src.rag.ingestion\npython -m src.rag.index build", language="bash")
        else:
            show_result(message["result"])


st.set_page_config(page_title="Python Docs Assistant", page_icon="🐍")
st.title("Python Docs Assistant")
st.caption("Search selected Python 3.12 documentation and perform simple calculations.")
st.info("Each question is processed independently. Check answers against the retrieved sources.")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    show_message(message)

if question := st.chat_input("Ask a Python documentation or arithmetic question"):
    user_message = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    show_message(user_message)

    try:
        settings = load_settings()
    except ValueError as exc:
        assistant_message = {
            "role": "assistant",
            "error": f"Invalid generation configuration: {exc}",
        }
    else:
        try:
            signature = index_signature()
            agent = load_agent(signature, settings)
        except (OSError, ValueError, KeyError):
            logger.exception("Unable to load the documentation index")
            assistant_message = {
                "role": "assistant",
                "error": "The documentation index is missing or invalid. Rebuild it and try again.",
                "setup_required": True,
            }
        except Exception:
            logger.exception("Unable to initialize the agent")
            assistant_message = {
                "role": "assistant",
                "error": "The assistant could not start. Please try again.",
            }
        else:
            try:
                with st.spinner("Working on your question..."):
                    result = agent.invoke({"question": question})
                assistant_message = {"role": "assistant", "result": result}
            except Exception:
                logger.exception("Agent workflow failed")
                assistant_message = {
                    "role": "assistant",
                    "error": "The question could not be processed. Please try again.",
                }

    st.session_state.messages.append(assistant_message)
    show_message(assistant_message)