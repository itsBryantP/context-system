"""Markdown extractor — passthrough with frontmatter parsing."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ctx.extractors.base import Extractor
from ctx.schema import Source, SourceType


class MarkdownExtractor(Extractor):
    def can_handle(self, source: Source) -> bool:
        return source.type == SourceType.MARKDOWN

    def extract(self, source: Source, output_dir: Path) -> list[Path]:
        if not source.path:
            raise ValueError("Markdown source requires a 'path'")

        src = Path(source.path).expanduser()
        files = sorted(src.parent.glob(src.name)) if "*" in str(src) else [src]

        if not files:
            raise FileNotFoundError(f"No files matched: {source.path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []

        for md_path in files:
            md_path = md_path.resolve()
            if not md_path.exists():
                raise FileNotFoundError(f"File not found: {md_path}")

            body, _tags = _strip_frontmatter(md_path.read_text())
            out_path = output_dir / md_path.name
            out_path.write_text(body)
            created.append(out_path)

        return created


def _strip_frontmatter(content: str) -> tuple[str, list[str]]:
    """Remove YAML frontmatter and return (body, tags).

    Tags are extracted for the caller but not embedded in the output —
    per-file tag inheritance into chunk metadata is a Phase 4 enhancement.
    """
    tags: list[str] = []
    if not content.startswith("---"):
        return content, tags

    end = content.find("\n---", 3)
    if end == -1:
        return content, tags

    frontmatter_text = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")

    try:
        fm = yaml.safe_load(frontmatter_text) or {}
        raw = fm.get("tags", [])
        if isinstance(raw, list):
            tags = [str(t) for t in raw]
        elif raw:
            tags = [str(raw)]
    except Exception:
        pass

    return body, tags
