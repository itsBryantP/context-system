"""Tests for chunking strategies."""

from pathlib import Path

import pytest

from ctx.chunker.base import Chunk, count_tokens, slugify
from ctx.chunker.heading import HeadingChunker, _is_orphan_heading, _extract_doc_title
from ctx.chunker.fixed import FixedChunker

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample-module"


def test_count_tokens():
    tokens = count_tokens("Hello, world!")
    assert isinstance(tokens, int)
    assert tokens > 0


def test_slugify():
    assert slugify("GET /users") == "get-users"
    assert slugify("API Endpoints") == "api-endpoints"
    assert slugify("  Hello World  ") == "hello-world"


class TestHeadingChunker:
    def test_basic_chunking(self):
        content = SAMPLE.joinpath("content/overview.md").read_text()
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="sample-module",
            source_file="content/overview.md",
            tags=["test"],
            version="1.0.0",
            max_tokens=500,
            heading_level=2,
        )
        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_ids_are_deterministic(self):
        content = "## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n"
        chunker = HeadingChunker()
        kwargs = dict(
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, heading_level=2,
        )
        chunks1 = chunker.chunk(content, **kwargs)
        chunks2 = chunker.chunk(content, **kwargs)
        assert [c.id for c in chunks1] == [c.id for c in chunks2]

    def test_chunk_metadata(self):
        content = "## Section\n\nSome content here.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=["api"], version="2.0.0", max_tokens=500, heading_level=2,
        )
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.module == "test"
        assert chunk.metadata["tags"] == ["api"]
        assert chunk.metadata["version"] == "2.0.0"
        assert "token_count" in chunk.metadata

    def test_section_path(self):
        content = "## Architecture\n\nLayered design.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, heading_level=2,
        )
        assert chunks[0].section_path == ["Architecture"]

    def test_preamble_preserved(self):
        content = "Intro paragraph.\n\n## Section\n\nContent.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, heading_level=2,
        )
        assert len(chunks) == 2
        assert "Intro paragraph" in chunks[0].content

    def test_orphan_preamble_dropped(self):
        """File with only an H1 before the first H2 should not emit a title-only chunk."""
        content = "# Title\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, heading_level=2,
        )
        assert len(chunks) == 2
        assert all("Section A" in c.content or "Section B" in c.content for c in chunks)
        # No chunk is just the title.
        assert not any(c.content.strip() == "# Title" for c in chunks)

    def test_empty_h2_dropped_when_has_h3_subsections(self):
        """An H2 with no body before its H3s should not emit a title-only chunk."""
        # Make the H2 section bigger than max_tokens so it triggers the sub-section path.
        big = "word " * 300
        content = f"## Parent\n\n### Sub1\n\n{big}\n\n### Sub2\n\n{big}\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, heading_level=2,
        )
        # Two sub-sections, no orphan Parent.
        assert len(chunks) == 2
        contents = [c.content for c in chunks]
        assert not any(c.strip() == "## Parent" for c in contents)
        # Parent is still the prefix in section_path.
        for c in chunks:
            assert c.section_path[0] == "Parent"

    def test_pure_heading_file_produces_no_chunks(self):
        content = "# Title\n\n## A\n\n## B\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, heading_level=2,
        )
        assert chunks == []

    def test_legitimate_preamble_kept(self):
        """Preamble with real content after H1 is still emitted as a chunk."""
        content = "# Title\n\nThis module explains X.\n\n## Section\n\nBody.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, heading_level=2,
        )
        assert len(chunks) == 2
        assert "This module explains X" in chunks[0].content


class TestOrphanHeadingHelper:
    @pytest.mark.parametrize("text,expected", [
        ("# Title", True),
        ("# Title\n", True),
        ("## A\n\n### B", True),
        ("# Title\n\nParagraph.", False),
        ("## Section\n\n- item", False),
        ("   ", True),  # vacuous — no non-empty lines
        ("", True),
        ("#Not a heading (no space)", False),
        ("# Title\n\n<!-- comment -->", False),
    ])
    def test_is_orphan_heading(self, text, expected):
        assert _is_orphan_heading(text) == expected

    def test_extract_doc_title_h1(self):
        assert _extract_doc_title("# Main Title\n\n## Section") == "Main Title"

    def test_extract_doc_title_no_h1(self):
        assert _extract_doc_title("## Only H2\n\nContent") is None

    def test_extract_doc_title_picks_first(self):
        assert _extract_doc_title("# First\n\n# Second") == "First"


class TestFixedChunker:
    def test_basic_chunking(self):
        # Generate content that exceeds max_tokens
        paragraphs = [f"Paragraph {i}. " + "word " * 50 for i in range(10)]
        content = "\n\n".join(paragraphs)
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=100, overlap_tokens=20,
        )
        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_single_paragraph(self):
        content = "Just one paragraph of text."
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        assert len(chunks) == 1

    def test_empty_content(self):
        chunker = FixedChunker()
        chunks = chunker.chunk(
            "",
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        assert chunks == []

    def test_chunk_indices(self):
        paragraphs = [f"Paragraph {i}. " + "word " * 50 for i in range(10)]
        content = "\n\n".join(paragraphs)
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=100,
        )
        for i, chunk in enumerate(chunks):
            assert chunk.metadata["chunk_index"] == i
            assert chunk.metadata["total_chunks"] == len(chunks)

    def test_oversized_paragraph_split_at_newlines(self):
        """A paragraph >max_tokens with internal \\n lines is split per line."""
        # Build a paragraph where each line ≤50 tokens, total >500 tokens.
        lines = [f"Line {i}: " + "word " * 40 for i in range(20)]
        content = "\n".join(lines)  # single paragraph, no \n\n
        assert count_tokens(content) > 500
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, overlap_tokens=50,
        )
        assert len(chunks) > 1
        # Invariant: every chunk ≤ max_tokens (with small slack for overlap)
        for chunk in chunks:
            assert chunk.metadata["token_count"] <= 550, (
                f"chunk {chunk.id} has {chunk.metadata['token_count']} tokens, "
                f"expected ≤550"
            )

    def test_oversized_paragraph_token_window_fallback(self):
        """A paragraph with no breakpoints falls back to token-window splitting."""
        # No newlines, no sentence terminators — only token-window works.
        content = "aaaaaaaaaa " * 500  # one long run, >500 tokens
        assert count_tokens(content) > 500
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, overlap_tokens=50,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["token_count"] <= 550

    def test_oversized_sentence_split(self):
        """A paragraph with sentence endings but no newlines splits at sentences."""
        sentences = ["Sentence " + str(i) + ". " + "word " * 40 + "." for i in range(15)]
        content = " ".join(sentences)  # one paragraph, sentence-terminated
        assert count_tokens(content) > 500
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500, overlap_tokens=50,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["token_count"] <= 550

    def test_normal_paragraphs_unaffected(self):
        """Normal paragraphs still split on \\n\\n boundaries."""
        content = "Para one.\n\nPara two.\n\nPara three."
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        assert len(chunks) == 1
        assert "Para one" in chunks[0].content
        assert "Para three" in chunks[0].content
