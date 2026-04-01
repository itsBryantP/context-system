"""Fixed token-size window chunking with paragraph-aware boundaries."""

from __future__ import annotations

from ctx.chunker.base import Chunk, ChunkStrategy, count_tokens, slugify, get_encoder


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
        **kwargs,
    ) -> list[Chunk]:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not paragraphs:
            return []

        section_path = _section_path or []
        chunks: list[Chunk] = []
        current_paragraphs: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)

            if current_tokens + para_tokens > max_tokens and current_paragraphs:
                # Emit current chunk
                chunks.append(self._make_chunk(
                    "\n\n".join(current_paragraphs),
                    section_path, len(chunks),
                    module_name=module_name,
                    source_file=source_file,
                    tags=tags, version=version,
                ))
                # Build overlap from trailing paragraphs
                current_paragraphs, current_tokens = self._build_overlap(
                    current_paragraphs, overlap_tokens
                )

            current_paragraphs.append(para)
            current_tokens += para_tokens

        # Emit final chunk
        if current_paragraphs:
            chunks.append(self._make_chunk(
                "\n\n".join(current_paragraphs),
                section_path, len(chunks),
                module_name=module_name,
                source_file=source_file,
                tags=tags, version=version,
            ))

        # Set total_chunks on all
        for chunk in chunks:
            chunk.metadata["chunk_index"] = chunks.index(chunk)
            chunk.metadata["total_chunks"] = len(chunks)

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
    ) -> Chunk:
        file_stem = source_file.rsplit("/", 1)[-1].removesuffix(".md")
        slug_parts = [file_stem] + [slugify(s) for s in section_path] + [str(index)]
        chunk_id = f"{module_name}/{'/'.join(slug_parts)}"

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
            },
        )
