"""Fixed token-size window chunking with paragraph-aware boundaries."""

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
    get_encoder,
    slugify,
)


class FixedChunker(ChunkStrategy):
    """Sliding window chunking that never splits mid-paragraph."""

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
        _section_path: list[str] | None = None,
        _doc_title: str | None = None,
        _file_id: str | None = None,
        _skip_chain: bool = False,
        **kwargs,
    ) -> list[Chunk]:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not paragraphs:
            return []

        section_path = _section_path or []
        doc_title = _doc_title or derive_doc_title(source_file)
        file_id = _file_id or compute_file_id(source_file)
        common = dict(
            module_name=module_name,
            source_file=source_file,
            tags=tags,
            version=version,
            doc_title=doc_title,
            file_id=file_id,
        )

        chunks: list[Chunk] = []
        current_paragraphs: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)

            if para_tokens > max_tokens:
                if current_paragraphs:
                    chunks.append(self._make_chunk(
                        "\n\n".join(current_paragraphs),
                        section_path, len(chunks), **common,
                    ))
                    current_paragraphs, current_tokens = [], 0

                for piece in _split_oversized_paragraph(para, max_tokens, overlap_tokens):
                    chunks.append(self._make_chunk(
                        piece, section_path, len(chunks), **common,
                    ))
                continue

            if current_tokens + para_tokens > max_tokens and current_paragraphs:
                chunks.append(self._make_chunk(
                    "\n\n".join(current_paragraphs),
                    section_path, len(chunks), **common,
                ))
                current_paragraphs, current_tokens = self._build_overlap(
                    current_paragraphs, overlap_tokens
                )

            current_paragraphs.append(para)
            current_tokens += para_tokens

        if current_paragraphs:
            chunks.append(self._make_chunk(
                "\n\n".join(current_paragraphs),
                section_path, len(chunks), **common,
            ))

        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        if not _skip_chain:
            apply_chain_metadata(chunks)

        return chunks

    def _build_overlap(
        self, paragraphs: list[str], overlap_tokens: int
    ) -> tuple[list[str], int]:
        """Take trailing paragraphs up to overlap_tokens for the next chunk's start."""
        overlap: list[str] = []
        tokens = 0
        for para in reversed(paragraphs):
            para_tokens = count_tokens(para)
            if tokens + para_tokens > overlap_tokens:
                break
            overlap.insert(0, para)
            tokens += para_tokens
        return overlap, tokens

    def _make_chunk(
        self,
        content: str,
        section_path: list[str],
        index: int,
        *,
        module_name: str,
        source_file: str,
        tags: list[str],
        version: str,
        doc_title: str,
        file_id: str,
    ) -> Chunk:
        file_stem = source_file.rsplit("/", 1)[-1].removesuffix(".md")
        slug_parts = [file_stem] + [slugify(s) for s in section_path] + [str(index)]
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
                "heading_level": None,
                "parent_section": section_path[-1] if section_path else None,
                "doc_title": doc_title,
                "file_id": file_id,
                "has_code": has_code,
                "language": language,
            },
        )


# ── Oversized paragraph splitter ──────────────────────────────────────────────


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _split_oversized_paragraph(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Split a paragraph exceeding max_tokens into pieces, each ≤ max_tokens.

    Tries, in order: single-newline split, sentence-boundary split, token-window.
    The token-window fallback always terminates for any input.
    """
    lines = text.split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) > 1 and all(count_tokens(l) <= max_tokens for l in non_empty):
        return _pack_pieces(lines, "\n", max_tokens, overlap_tokens)

    sentences = _SENTENCE_RE.split(text)
    non_empty_sents = [s for s in sentences if s.strip()]
    if len(non_empty_sents) > 1 and all(
        count_tokens(s) <= max_tokens for s in non_empty_sents
    ):
        return _pack_pieces(sentences, " ", max_tokens, overlap_tokens)

    return _token_window_split(text, max_tokens, overlap_tokens)


def _pack_pieces(
    pieces: list[str],
    joiner: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Accumulate pieces into chunks ≤ max_tokens with overlap carryover."""
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for piece in pieces:
        if not piece.strip() and not current:
            continue
        piece_tokens = count_tokens(piece) if piece.strip() else 0

        if current_tokens + piece_tokens > max_tokens and current:
            chunks.append(joiner.join(current).strip())
            overlap: list[str] = []
            ot = 0
            for p in reversed(current):
                pt = count_tokens(p) if p.strip() else 0
                if ot + pt > overlap_tokens:
                    break
                overlap.insert(0, p)
                ot += pt
            current = overlap
            current_tokens = ot

        current.append(piece)
        current_tokens += piece_tokens

    if current:
        joined = joiner.join(current).strip()
        if joined:
            chunks.append(joined)

    return chunks


def _token_window_split(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Slide a max_tokens-wide window over the token stream. Always terminates."""
    encoder = get_encoder()
    tokens = encoder.encode(text)
    if len(tokens) <= max_tokens:
        return [text]

    step = max(max_tokens - overlap_tokens, 1)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunks.append(encoder.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start += step
    return chunks
