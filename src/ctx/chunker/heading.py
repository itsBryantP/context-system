"""Heading-based semantic chunking strategy.

Splits markdown at heading boundaries, preserving document structure.
Falls back to fixed-size splitting when sections exceed max_tokens.
"""

from __future__ import annotations

import re

from ctx.chunker.base import (
    Chunk,
    ChunkStrategy,
    apply_chain_metadata,
    compute_file_id,
    count_tokens,
    derive_doc_title,
    detect_code,
    slugify,
)


_HEADING_ONLY_RE = re.compile(r"^#{1,6}\s+\S")
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _is_orphan_heading(text: str) -> bool:
    """Return True if text contains only markdown heading lines (any level).

    Blank lines are tolerated. An empty string is considered an orphan
    (vacuously — no non-heading content to preserve).
    """
    stripped = text.strip()
    if not stripped:
        return True
    for line in stripped.split("\n"):
        line = line.strip()
        if not line:
            continue
        if not _HEADING_ONLY_RE.match(line):
            return False
    return True


def _extract_doc_title(content: str) -> str | None:
    """Return the first `# heading` line's text, or None if no H1 present."""
    match = _H1_RE.search(content)
    return match.group(1).strip() if match else None


class HeadingChunker(ChunkStrategy):
    """Split markdown at heading boundaries."""

    def chunk(
        self,
        content: str,
        *,
        module_name: str,
        source_file: str,
        tags: list[str],
        version: str,
        max_tokens: int = 500,
        overlap_tokens: int = 50,
        heading_level: int = 2,
        **kwargs,
    ) -> list[Chunk]:
        doc_title = _extract_doc_title(content) or derive_doc_title(source_file)
        file_id = compute_file_id(source_file)

        sections = self._split_at_level(content, heading_level)
        chunks: list[Chunk] = []

        common = dict(
            module_name=module_name,
            source_file=source_file,
            tags=tags,
            version=version,
            doc_title=doc_title,
            file_id=file_id,
        )

        for section_path, section_content in sections:
            if _is_orphan_heading(section_content):
                continue

            token_count = count_tokens(section_content)

            if token_count <= max_tokens:
                chunks.append(self._make_chunk(section_content, section_path, **common))
            else:
                sub_sections = self._split_at_level(section_content, heading_level + 1)
                if len(sub_sections) > 1:
                    for sub_path, sub_content in sub_sections:
                        if _is_orphan_heading(sub_content):
                            continue
                        full_path = section_path + sub_path
                        if count_tokens(sub_content) <= max_tokens:
                            chunks.append(self._make_chunk(sub_content, full_path, **common))
                        else:
                            chunks.extend(self._fixed_fallback(
                                sub_content, full_path,
                                max_tokens=max_tokens,
                                overlap_tokens=overlap_tokens,
                                **common,
                            ))
                else:
                    chunks.extend(self._fixed_fallback(
                        section_content, section_path,
                        max_tokens=max_tokens,
                        overlap_tokens=overlap_tokens,
                        **common,
                    ))

        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        apply_chain_metadata(chunks)

        return chunks

    def _split_at_level(
        self, content: str, level: int
    ) -> list[tuple[list[str], str]]:
        """Split content at a given heading level. Returns (section_path, content) pairs.

        Orphan preambles (content before the first heading at `level` that is itself
        only heading lines) are dropped.
        """
        pattern = re.compile(rf"^(#{{{level}}})\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        if not matches:
            return [([], content)]

        sections: list[tuple[list[str], str]] = []

        preamble = content[: matches[0].start()].strip()
        if preamble and not _is_orphan_heading(preamble):
            sections.append(([], preamble))

        for i, match in enumerate(matches):
            heading_text = match.group(2).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()
            sections.append(([heading_text], section_content))

        return sections

    def _make_chunk(
        self,
        content: str,
        section_path: list[str],
        *,
        module_name: str,
        source_file: str,
        tags: list[str],
        version: str,
        doc_title: str,
        file_id: str,
    ) -> Chunk:
        file_stem = source_file.rsplit("/", 1)[-1].removesuffix(".md")
        slug_parts = [file_stem] + [slugify(s) for s in section_path]
        chunk_id = f"{module_name}/{'/'.join(slug_parts)}"

        has_code, language = detect_code(content)

        return Chunk(
            id=chunk_id,
            module=module_name,
            source_file=source_file,
            section_path=section_path,
            content=content,
            metadata={
                "tags": tags,
                "version": version,
                "heading_level": len(section_path),
                "parent_section": section_path[-2] if len(section_path) >= 2 else None,
                "doc_title": doc_title,
                "file_id": file_id,
                "has_code": has_code,
                "language": language,
            },
        )

    def _fixed_fallback(
        self,
        content: str,
        section_path: list[str],
        *,
        module_name: str,
        source_file: str,
        tags: list[str],
        version: str,
        doc_title: str,
        file_id: str,
        max_tokens: int,
        overlap_tokens: int,
    ) -> list[Chunk]:
        """Fall back to paragraph-aware fixed splitting for oversized sections."""
        from ctx.chunker.fixed import FixedChunker

        return FixedChunker().chunk(
            content,
            module_name=module_name,
            source_file=source_file,
            tags=tags,
            version=version,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            _section_path=section_path,
            _doc_title=doc_title,
            _file_id=file_id,
            _skip_chain=True,
        )
