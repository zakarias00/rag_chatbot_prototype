from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FIELDS = ("id", "path", "title", "source_url", "python_version", "retrieved_at", "license")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
WORD = re.compile(r"\S+")


def slugify(value: str) -> str:
    """Create a stable identifier from a section title."""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-") or "section"


def sections(text: str, title: str):
    """Yield Markdown section headings and bodies without treating code as headings."""
    heading, body, fence_char, fence_len = title, [], None, 0
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line)
        if marker:
            mark = marker.group(1)
            if fence_char is None:
                fence_char, fence_len = mark[0], len(mark)
            elif mark[0] == fence_char and len(mark) >= fence_len:
                fence_char, fence_len = None, 0
            body.append(line)
            continue
        match = HEADING.match(line.rstrip()) if fence_char is None else None
        if match:
            if "".join(body).strip():
                yield heading, "".join(body).strip()
            heading, body = match.group(2), []
        else:
            body.append(line)
    if "".join(body).strip():
        yield heading, "".join(body).strip()


def split_text(text: str, max_words: int = 400, overlap: int = 40):
    """Split on word boundaries, preserving whitespace and fenced code blocks. """
    if max_words <= 0 or not 0 <= overlap < max_words:
        raise ValueError("max_words must be positive and overlap must be in [0, max_words)")
    words = list(WORD.finditer(text))
    fences, start_fence, fence_char, fence_len, offset = [], None, None, 0, 0
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line)
        if marker:
            mark = marker.group(1)
            if start_fence is None:
                start_fence, fence_char, fence_len = offset, mark[0], len(mark)
            elif mark[0] == fence_char and len(mark) >= fence_len:
                fences.append((start_fence, offset + len(line)))
                start_fence, fence_char, fence_len = None, None, 0
        offset += len(line)
    if start_fence is not None:
        fences.append((start_fence, len(text)))
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        if end < len(words):
            for fence_begin, fence_end in fences:
                if fence_begin <= words[end - 1].start() < fence_end:
                    while end < len(words) and words[end].start() < fence_end:
                        end += 1
                    break
        start_offset = words[start].start()
        line_start = text.rfind("\n", 0, start_offset) + 1
        if not text[line_start:start_offset].strip():
            start_offset = line_start
        yield text[start_offset:words[end - 1].end()]
        if end == len(words):
            break
        next_start = end - overlap
        for fence_begin, fence_end in fences:
            if fence_begin < words[next_start].start() < fence_end:
                while next_start > start and words[next_start - 1].start() >= fence_begin:
                    next_start -= 1
                break
        start = next_start if next_start > start else end


def ingest(manifest_path: Path, output_path: Path, project_root: Path = PROJECT_ROOT,
           max_words: int = 400, overlap: int = 40) -> int:
    """Read a source manifest, split each document into chunks, and write JSONL output."""

    manifest_path, output_path, root = Path(manifest_path), Path(output_path), Path(project_root).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("Source manifest must be a nonempty JSON array")
    seen_ids, chunks = set(), []
    for source in manifest:
        if not isinstance(source, dict) or any(not isinstance(source.get(k), str) or not source[k].strip() for k in REQUIRED_FIELDS):
            raise ValueError(f"Every source needs nonempty string fields: {', '.join(REQUIRED_FIELDS)}")
        source_id = source["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id) or source_id in seen_ids:
            raise ValueError(f"Invalid or duplicate source id: {source_id}")
        seen_ids.add(source_id)
        path = (root / source["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Source path must remain inside project root: {source['path']}")
        text = path.read_text(encoding="utf-8")
        section_counts = {}
        for heading, body in sections(text, source["title"]):
            slug = slugify(heading)
            section_counts[slug] = section_counts.get(slug, 0) + 1
            section_id = f"{slug}-{section_counts[slug]}"
            for number, chunk in enumerate(split_text(body, max_words, overlap), 1):
                chunks.append({
                    "document_id": source_id,
                    "chunk_id": f"{source_id}--{section_id}--{number:03d}",
                    "title": source["title"], "section": heading, "source_path": source["path"],
                    "source_url": source["source_url"], "source_revision": source.get("source_revision", ""),
                    "python_version": source["python_version"], "retrieved_at": source["retrieved_at"],
                    "license": source["license"], "text": chunk,
                })
    if not chunks:
        raise ValueError("No nonempty text found in the source documents")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data/sources.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/processed/chunks.jsonl")
    parser.add_argument("--max-words", type=int, default=400)
    parser.add_argument("--overlap", type=int, default=40)
    args = parser.parse_args()
    count = ingest(args.manifest, args.output, max_words=args.max_words, overlap=args.overlap)
    print(f"Wrote {count} chunks to {args.output}")


if __name__ == "__main__":
    main()
