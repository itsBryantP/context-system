"""JSONL output writer for chunked content."""

from __future__ import annotations

import json
from pathlib import Path

from ctx.chunker.base import Chunk


def chunks_to_jsonl(chunks: list[Chunk]) -> str:
    """Serialize a list of Chunks to JSONL string."""
    lines = []
    for chunk in chunks:
        record = {
            "id": chunk.id,
            "module": chunk.module,
            "source_file": chunk.source_file,
            "section_path": chunk.section_path,
            "content": chunk.content,
            "metadata": chunk.metadata,
        }
        lines.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(lines) + "\n" if lines else ""


def write_jsonl(chunks: list[Chunk], output_path: Path) -> Path:
    """Write chunks to a JSONL file. Creates parent directories as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(chunks_to_jsonl(chunks))
    return output_path


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file and return list of dicts."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records
