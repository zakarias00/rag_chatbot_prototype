# Agentic RAG: Python documentation assistant

## Requirements and setup

Install Python 3.12, then run from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows, use `.venv\Scripts\activate` instead. Direct dependencies are
pinned in `pyproject.toml`; transitive dependencies are not yet locked.

## Run the UI

```bash
streamlit run app.py
```

The page explains the planned assistant; it does not answer questions yet.

## Prepare and query the corpus

The curated corpus covers `venv`, `pathlib`, `json`, `csv`, `logging` and
exceptions from the Python 3.12.8 documentation. The excerpts are adapted,
not complete manuals. For source revision, attribution, and licensing details
see `data/sources.json` and `data/README.md`.

With the virtual environment activated, from the repository root:

```bash
python -m rag_chatbot.rag.ingestion
python -m rag_chatbot.rag.index build
python -m rag_chatbot.rag.index query 'What is the difference between json.dump and json.dumps?' --k 3
```

The ingestion step splits the Markdown sources into attributed chunks with
deterministic identifiers. The index uses TF-IDF and cosine similarity. Query
results contain text, source metadata and similarity scores; the scores are
not probabilities or guarantees of correctness. Generated files in
`data/processed/` are ignored by Git. Re-run ingestion and the index build
after changing a source or the manifest. Once dependencies are installed, no
network access is required for these commands.

To add a source, create a Markdown file under `data/raw/` and add an entry to
`data/sources.json` following the existing metadata fields. Use descriptive
headings and ensure the source license permits the intended use. Run the
commands above to regenerate the index.

## Run tests

```bash
python -m pytest -q
```
