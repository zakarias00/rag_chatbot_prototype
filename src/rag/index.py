"""Build and search a reusable local TF-IDF index of ingested chunks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.preprocessing import normalize

from .ingestion import PROJECT_ROOT

DEFAULT_CHUNKS = PROJECT_ROOT / "data/processed/chunks.jsonl"
DEFAULT_INDEX = PROJECT_ROOT / "data/processed/index"
TOKEN = re.compile(r"(?u)\b\w+(?:\.\w+)*\b")


def tokenize(text: str) -> list[str]:
    """Index Python names as a whole and as dotted/underscore-separated words."""
    result = []

    for token in TOKEN.findall(text):
        result.append(token)

        if "." in token or "_" in token:
            result.extend(part for part in re.split(r"[._]", token) if part)

    return result


def load_chunks(path: Path) -> tuple[bytes, list[dict]]:
    content = Path(path).read_bytes()
    chunks = [
        json.loads(line)
        for line in content.decode("utf-8").splitlines()
        if line.strip()
    ]

    if not chunks or any(
        not isinstance(c, dict)
        or not isinstance(c.get("text"), str)
        or not c["text"].strip()
        or not isinstance(c.get("chunk_id"), str)
        or not c["chunk_id"].strip()
        for c in chunks
    ):
        raise ValueError(
            "Chunk file must contain nonempty JSONL records "
            "with text and chunk_id"
        )

    ids = [c["chunk_id"] for c in chunks]

    if len(ids) != len(set(ids)):
        raise ValueError("Chunk ids must be unique")

    return content, chunks


def build_index(
    chunks_path: Path = DEFAULT_CHUNKS,
    index_dir: Path = DEFAULT_INDEX,
) -> int:
    """Build an index from JSONL and persist it as JSON metadata and sparse NPZ."""
    content, chunks = load_chunks(chunks_path)

    vectorizer = TfidfVectorizer(
        tokenizer=tokenize,
        token_pattern=None,
        lowercase=True,
        dtype=np.float64,
    )

    texts = [
        f'{c.get("title", "")} {c.get("section", "")}\n{c["text"]}'
        for c in chunks
    ]

    matrix = vectorizer.fit_transform(texts).tocsr()

    metadata = {
        "format_version": 1,
        "chunks_sha256": hashlib.sha256(content).hexdigest(),
        "vocabulary": vectorizer.vocabulary_,
        "idf": vectorizer.idf_.tolist(),
    }

    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    sparse.save_npz(index_dir / "matrix.npz", matrix)

    (index_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    return len(chunks)


class DocumentationIndex:
    """Load once, then reuse for multiple questions."""

    def __init__(
        self,
        chunks_path: Path = DEFAULT_CHUNKS,
        index_dir: Path = DEFAULT_INDEX,
    ):
        content, self.chunks = load_chunks(chunks_path)
        index_dir = Path(index_dir)

        metadata = json.loads(
            (index_dir / "metadata.json").read_text(encoding="utf-8")
        )

        if metadata.get("format_version") != 1:
            raise ValueError("Unsupported index format; rebuild the index")

        if metadata.get("chunks_sha256") != hashlib.sha256(content).hexdigest():
            raise ValueError("Chunks have changed since indexing; rebuild the index")

        self.matrix = sparse.load_npz(index_dir / "matrix.npz").tocsr()
        vocabulary = metadata["vocabulary"]
        self.idf = np.asarray(metadata["idf"], dtype=np.float64)

        if (
            self.matrix.shape != (len(self.chunks), len(vocabulary))
            or len(self.idf) != len(vocabulary)
        ):
            raise ValueError(
                "Index dimensions do not match its metadata; rebuild the index"
            )

        self.vectorizer = CountVectorizer(
            vocabulary=vocabulary,
            tokenizer=tokenize,
            token_pattern=None,
            lowercase=True,
        )

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Return positive-scoring chunks, highest cosine similarity first."""
        if not query.strip():
            raise ValueError("Query must not be empty")

        if k < 1:
            raise ValueError("k must be at least 1")

        counts = self.vectorizer.transform([query])

        if counts.nnz == 0:
            return []

        query_vector = normalize(
            counts.multiply(self.idf).tocsr(),
            norm="l2",
        )

        scores = (self.matrix @ query_vector.T).toarray().ravel()

        # Keep the original chunk order when scores are equal.
        order = np.argsort(-scores, kind="stable")

        return [
            {**self.chunks[i], "score": float(scores[i])}
            for i in order[:k]
            if scores[i] > 0
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build",
        help="Build an index from chunk JSONL",
    )
    build.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    build.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)

    query = subparsers.add_parser(
        "query",
        help="Search an existing index",
    )
    query.add_argument("query", help="Question or search query")
    query.add_argument("--k", type=int, default=5)
    query.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    query.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)

    args = parser.parse_args()

    if args.command == "build":
        count = build_index(args.chunks, args.index_dir)
        print(f"Indexed {count} chunks in {args.index_dir}")
    else:
        results = DocumentationIndex(
            args.chunks,
            args.index_dir,
        ).search(args.query, args.k)

        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()