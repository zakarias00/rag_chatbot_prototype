# Agentic RAG: Python documentation assistant

A Python and LangGraph prototype for answering questions about the Python
standard library using retrieved documentation and tools.

## Requirements

- Python 3.12

## Setup

From the repository root, create and activate a virtual environment, then
install the project and its development dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.
The direct dependencies are pinned in `pyproject.toml`; transitive dependencies
are not yet locked, so separate installations may resolve different versions.

## Run

```bash
streamlit run app.py
```

To stop the server, press Ctrl+C in the terminal.