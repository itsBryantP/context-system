"""Definition-based chunking for glossaries, FAQs, and reference docs."""

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

# H3/H4 headings used as definition boundaries
_HEADING_RE = re.compile(r"^(#{3,4})\s+(.+)$", re.MULTILINE)

# **Term**: description  or  **Term** — description
_BOLD_TERM_RE = re.compile(r"^\*\*(.+?)\*\*[:\s—–-]\s*(.*)", re.MULTILINE)


class DefinitionChunker(ChunkStrategy):
    """One chunk per definition (or grouped small definitions up to max_tokens).

    Detection order:
    1. H3/H4 heading boundaries — each heading + body is one definition
    2. **Bold-term** patterns — **Term**: description blocks
    3. Falls back to FixedChunker if no definitions are detected
    """

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
        **kwargs,
    ) -> list[Chunk]:
        from ctx.chunker.heading import _extract_doc_title

        doc_title = _extract_doc_title(content) or derive_doc_title(source_file)
        file_id = compute_file_id(source_file)

        defs = _extract_heading_defs(content)
        if len(defs) < 2:
            defs = _extract_bold_defs(content)
        if not defs:
            from ctx.chunker.fixed import FixedChunker
            return FixedChunker().chunk(
                content,
                module_name=module_name,
                source_file=source_file,
                tags=tags,
                version=version,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
                _doc_title=doc_title,
                _file_id=file_id,
            )

        groups = _group_definitions(defs, max_tokens)
        file_stem = source_file.rsplit("/", 1)[-1].removesuffix(".md")
        chunks: list[Chunk] = []

        for group in groups:
            combined = "\n\n".join(text for _, text in group)
            term = group[0][0]

            if count_tokens(combined) > max_tokens:
                from ctx.chunker.fixed import FixedChunker
                sub = FixedChunker().chunk(
                    combined,
                    module_name=module_name,
                    source_file=source_file,
                    tags=tags,
                    version=version,
                    max_tokens=max_tokens,
                    overlap_tokens=overlap_tokens,
                    _section_path=[term],
                    _doc_title=doc_title,
                    _file_id=file_id,
                    _skip_chain=True,
                )
                chunks.extend(sub)
            else:
                chunk_id = f"{module_name}/{file_stem}/{slugify(term)}"
                has_code, language = detect_code(combined)
                chunks.append(Chunk(
                    id=chunk_id,
                    module=module_name,
                    source_file=source_file,
                    section_path=[term],
                    content=combined,
                    metadata={
                        "tags": tags,
                        "version": version,
                        "heading_level": None,
                        "parent_section": None,
                        "doc_title": doc_title,
                        "file_id": file_id,
                        "has_code": has_code,
                        "language": language,
                    },
                ))

        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        apply_chain_metadata(chunks)

        return chunks


def _extract_heading_defs(content: str) -> list[tuple[str, str]]:
    """Split on H3/H4 headings; return (term, full-block) pairs."""
    matches = list(_HEADING_RE.finditer(content))
    if not matches:
        return []
    defs: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        term = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        defs.append((term, content[start:end].strip()))
    return defs


def _extract_bold_defs(content: str) -> list[tuple[str, str]]:
    """Collect **Term**: ... blocks, each term + following non-term lines."""
    lines = content.splitlines()
    defs: list[tuple[str, str]] = []
    current_term: str | None = None
    current_lines: list[str] = []

    for line in lines:
        m = _BOLD_TERM_RE.match(line)
        if m:
            if current_term is not None:
                defs.append((current_term, "\n".join(current_lines).strip()))
            current_term = m.group(1).strip()
            current_lines = [line]
        elif current_term is not None:
            current_lines.append(line)

    if current_term is not None and current_lines:
        defs.append((current_term, "\n".join(current_lines).strip()))

    return defs


def _group_definitions(
    defs: list[tuple[str, str]], max_tokens: int
) -> list[list[tuple[str, str]]]:
    """Group small definitions together up to max_tokens to avoid micro-chunks."""
    groups: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0

    for term, text in defs:
        t = count_tokens(text)
        if current and current_tokens + t > max_tokens:
            groups.append(current)
            current = []
            current_tokens = 0
        current.append((term, text))
        current_tokens += t

    if current:
        groups.append(current)

    return groups
