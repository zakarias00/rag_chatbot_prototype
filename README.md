# Agentic RAG Chatbot — Python Documentation Assistant

A small **LangGraph-based agentic RAG prototype** that answers questions about selected Python 3.12 documentation and performs simple calculations. Built as a medior AI Engineer take-home project, it uses local documentation and **does not require a paid API**.

## What it does

- Searches Python documentation for `json`, `pathlib`, `venv`, `csv`, `logging`, and exception handling.
- Splits multi-part questions into retrieval needs, retrieves and selects relevant evidence, and provides source citations.
- Routes arithmetic requests to a calculator tool; can combine documentation and calculation steps.
- Abstains when there is not enough supporting evidence and records a workflow trace.
- Provides a **Streamlit UI** showing the answer, sources, retrieved evidence, and graph steps.
- Supports two answer backends: **dummy** (deterministic excerpts) and **Ollama** (optional local LLM, with an extractive fallback when generation fails).

## Architecture

The main LangGraph workflow has eight nodes: `plan`, `retrieve`, `assess_evidence`, `refine_query`, `calculate`, `generate_answer`, `abstain`, and `finalize`. Conditional edges select the appropriate steps and allow a bounded retrieval retry.

A separate three-node RAG subgraph handles documentation search and evidence selection. The corpus is ingested from Markdown, divided into attributed chunks, and indexed with **TF-IDF and cosine similarity**. Retrieval combines query decomposition, candidate ranking, and evidence diversification. The non-retrieval tool is a structured calculator.

| Location | Purpose |
| --- | --- |
| `app.py` | Streamlit chat interface |
| `src/graph.py`, `src/nodes.py`, `src/state.py` | Main agent graph, routing, and state |
| `src/rag/querying.py`, `src/rag/evidence.py` | Multi-part search and lightweight evidence checks |
| `src/tools/math_parser.py` | Recognizes supported calculations without executing code |
| `src/rag/` | Ingestion, TF-IDF index, retrieval, and RAG subgraph |
| `src/tools/` | Documentation-search and calculator tools |
| `src/generation/` | Deterministic generator, Ollama integration, fallback |
| `src/config.py` | Environment-based generator configuration |
| `data/raw/`, `data/sources.json` | Documentation excerpts and source metadata |
| `tests/` | Automated unit and integration tests |
| `evaluation/` | Question datasets, functional evaluator, load test, reports |

**Design trade-off:** TF-IDF and a deterministic baseline keep the prototype lightweight, explainable, and reproducible. Ollama can produce more natural answers, but needs local compute and is evaluated separately from the deterministic baseline.

## Run locally

Requirements: **Python 3.12**. Run the following commands from the repository root after cloning it:

```bash
python3.12 -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'

# Build the documentation corpus and search index
python -m src.rag.ingestion
python -m src.rag.index build
```

### Option A — deterministic mode (no Ollama required)

```bash
RAG_GENERATOR=dummy streamlit run app.py
```

### Option B — local Ollama model

Install [Ollama](https://ollama.com/), start its service, and download a model:

```bash
ollama pull qwen3:1.7b
RAG_GENERATOR=ollama OLLAMA_MODEL=qwen3:1.7b streamlit run app.py
```

The smaller 1.7B model is a practical starting point for an **8 GB MacBook**. The app's default generator is Ollama; set `RAG_GENERATOR=dummy` to run without it. When Ollama is unreachable or its output fails citation validation, the application falls back to deterministic excerpts and displays a warning.

Open **http://localhost:8501**. You can also run a question in the terminal:

```bash
RAG_GENERATOR=dummy python -m src.graph "What does json.dumps return?"
```

## Docker

Build the image:

```bash
docker build -t agentic-rag-chatbot .
```

Run without Ollama:

```bash
docker run --rm -p 8501:8501 -e RAG_GENERATOR=dummy agentic-rag-chatbot
```

To connect a Docker Desktop container to **Ollama running on your Mac**:

```bash
docker run --rm -p 8501:8501 \
  -e RAG_GENERATOR=ollama \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=qwen3:1.7b \
  agentic-rag-chatbot
```

The container rebuilds the documentation index during image creation. `127.0.0.1` **inside the container** does not refer to the Mac's Ollama service; the `host.docker.internal` address is intended for Docker Desktop. The Ollama service must be running and reachable from the container.

## Tests

```bash
python -m pytest -q
```

Tests cover ingestion/indexing, retrieval, graph routing, tools, generation/fallback, UI behavior, and evaluation helpers. Ollama behavior is mainly tested with mocked responses; a live Ollama run is a separate smoke test.

## Functional evaluation

The development dataset contains **15 questions** across documentation lookup, multi-source questions, calculation, and unsupported requests. It includes independently annotated evidence requirements so the evaluator can measure **per-answer-point evidence coverage**, rather than only exact chunk matches.

```bash
python -m evaluation.run_eval \
  --dataset evaluation/development_questions.jsonl \
  --output evaluation/results/functional.json
```

The saved final development report (`evaluation/results/functional_after_fix.json`) records:

| Metric | Result |
| --- | ---: |
| Evidence-point coverage@5 | 10/10 eligible questions |
| Complete final selected-evidence coverage | 10/10 |
| Correct tool selection and status | 15/15 each |
| Correct calculations | 3/3 |
| Execution errors | 0 |

**Interpretation:** These are **development-set results for the deterministic extractive backend**, not verified answer accuracy or an Ollama benchmark. The report contains no completed manual answer-quality reviews; coverage means the required evidence was present, not necessarily that every final answer expressed it correctly. The separate holdout set must be annotated with the current evaluation schema before using the updated evaluator.

Optional independently completed answer reviews can be supplied with `--reviews path/to/reviews.jsonl`.

## Load test

The load scenario uses a fixed mixture of **100 serial requests** by default, measures latency and tool timings, and records unexpected statuses. It uses the deterministic backend rather than live Ollama inference.

```bash
python -u -m evaluation.run_loaded_eval \
  --requests 100 --warmup 10 \
  --output evaluation/results/load.json
```

The script prints a summary after the run and writes the detailed JSON report.

## Repository notes

Commit source code, documentation, tests, the source manifest, question datasets, and **verified** evaluation reports. 
It does not contain `.venv/`, caches, system files, or `data/processed/` (generated chunks and index): these are recreated by the setup commands and are ignored by `.gitignore`. Source attribution is recorded in `data/sources.json.