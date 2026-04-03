"""Tests for the definition-based chunking strategy."""

from __future__ import annotations

import pytest

from ctx.chunker.definition import (
    DefinitionChunker,
    _extract_bold_defs,
    _extract_heading_defs,
    _group_definitions,
)
from ctx.chunker.base import Chunk

KWARGS = dict(
    module_name="test",
    source_file="content/glossary.md",
    tags=["api"],
    version="1.0.0",
    max_tokens=500,
    overlap_tokens=50,
)


class TestExtractHeadingDefs:
    def test_h3_boundaries(self):
        content = "### Term A\n\nDesc A.\n\n### Term B\n\nDesc B.\n"
        defs = _extract_heading_defs(content)
        assert len(defs) == 2
        assert defs[0][0] == "Term A"
        assert defs[1][0] == "Term B"

    def test_h4_boundaries(self):
        content = "#### Alpha\n\nDetails.\n\n#### Beta\n\nMore details.\n"
        defs = _extract_heading_defs(content)
        assert len(defs) == 2
        assert defs[0][0] == "Alpha"

    def test_no_matching_headings_returns_empty(self):
        content = "## Section\n\nSome content.\n"
        defs = _extract_heading_defs(content)
        assert defs == []

    def test_single_heading_returns_one(self):
        content = "### Only one\n\nContent.\n"
        defs = _extract_heading_defs(content)
        assert len(defs) == 1


class TestExtractBoldDefs:
    def test_colon_separator(self):
        content = "**API**: Application Programming Interface.\n**REST**: Representational State Transfer.\n"
        defs = _extract_bold_defs(content)
        assert len(defs) == 2
        assert defs[0][0] == "API"
        assert defs[1][0] == "REST"

    def test_dash_separator(self):
        content = "**Term** - A definition.\n"
        defs = _extract_bold_defs(content)
        assert len(defs) == 1
        assert defs[0][0] == "Term"

    def test_multiline_definition(self):
        content = "**Foo**: First line.\nContinued here.\n**Bar**: Other term.\n"
        defs = _extract_bold_defs(content)
        assert len(defs) == 2
        assert "Continued" in defs[0][1]

    def test_no_bold_terms_returns_empty(self):
        defs = _extract_bold_defs("Just plain text.\n\nMore text.\n")
        assert defs == []


class TestGroupDefinitions:
    def test_small_defs_grouped(self):
        defs = [("A", "short"), ("B", "short"), ("C", "short")]
        groups = _group_definitions(defs, max_tokens=500)
        assert len(groups) == 1  # all fit in one group

    def test_large_def_alone(self):
        long_text = "word " * 200  # ~200 tokens
        defs = [("Big", long_text), ("Small", "tiny")]
        groups = _group_definitions(defs, max_tokens=100)
        # Big is alone, Small starts a new group
        assert len(groups) == 2
        assert groups[0][0][0] == "Big"


class TestDefinitionChunker:
    def test_heading_based_glossary(self):
        content = (
            "### GET /users\n\nReturns a list of users.\n\n"
            "### POST /users\n\nCreates a new user.\n\n"
            "### DELETE /users/{id}\n\nDeletes the specified user.\n"
        )
        chunks = DefinitionChunker().chunk(content, **KWARGS)
        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_bold_term_glossary(self):
        content = (
            "**API**: Application Programming Interface.\n"
            "**SDK**: Software Development Kit.\n"
            "**REST**: Representational State Transfer.\n"
        )
        chunks = DefinitionChunker().chunk(content, **KWARGS)
        assert len(chunks) >= 1

    def test_fallback_to_fixed_when_no_defs(self):
        content = "Just some plain text without any definitions here.\n"
        chunks = DefinitionChunker().chunk(content, **KWARGS)
        assert len(chunks) >= 1

    def test_chunk_metadata_present(self):
        content = "### Alpha\n\nFirst.\n\n### Beta\n\nSecond.\n"
        chunks = DefinitionChunker().chunk(content, **KWARGS)
        for chunk in chunks:
            assert "token_count" in chunk.metadata
            assert "chunk_index" in chunk.metadata
            assert "total_chunks" in chunk.metadata
            assert chunk.metadata["tags"] == ["api"]
            assert chunk.metadata["version"] == "1.0.0"

    def test_chunk_ids_deterministic(self):
        content = "### Term A\n\nDesc.\n\n### Term B\n\nDesc.\n"
        c1 = DefinitionChunker().chunk(content, **KWARGS)
        c2 = DefinitionChunker().chunk(content, **KWARGS)
        assert [c.id for c in c1] == [c.id for c in c2]

    def test_oversized_definition_split(self):
        # A single definition that exceeds max_tokens
        long_body = "word " * 200
        content = f"### Huge Term\n\n{long_body}\n"
        chunks = DefinitionChunker().chunk(content, **{**KWARGS, "max_tokens": 50})
        assert len(chunks) > 1

    def test_small_defs_grouped_together(self):
        # Many tiny definitions should be batched into fewer chunks
        terms = "\n\n".join(f"### Term{i}\n\nShort." for i in range(20))
        chunks = DefinitionChunker().chunk(terms, **KWARGS)
        # 20 one-sentence defs should not produce 20 separate chunks
        assert len(chunks) < 20
