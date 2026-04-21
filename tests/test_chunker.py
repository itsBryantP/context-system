"""Tests for chunking strategies."""

from pathlib import Path

import pytest

from ctx.chunker.base import (
    Chunk,
    compute_file_id,
    count_tokens,
    derive_doc_title,
    detect_code,
    slugify,
)
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


class TestMetadataHelpers:
    def test_detect_code_python(self):
        content = "Before.\n\n```python\nx = 1\n```\n\nAfter."
        assert detect_code(content) == (True, "python")

    def test_detect_code_no_language(self):
        content = "```\nplain\n```"
        assert detect_code(content) == (True, None)

    def test_detect_code_multi_token_info(self):
        content = "```python {linenos=true}\nx=1\n```"
        assert detect_code(content) == (True, "python")

    def test_detect_code_hyphenated(self):
        content = "```objective-c\nNSLog(@\"x\");\n```"
        assert detect_code(content) == (True, "objective-c")

    def test_detect_code_multiple_blocks_first_wins(self):
        content = "```python\nx=1\n```\n\ntext\n\n```bash\necho hi\n```"
        assert detect_code(content) == (True, "python")

    def test_detect_code_no_fences(self):
        content = "Prose only, no code."
        assert detect_code(content) == (False, None)

    def test_detect_code_unclosed_fence(self):
        content = "```python\nx = 1\n(no closing fence)"
        assert detect_code(content) == (False, None)

    def test_compute_file_id_stable(self):
        a = compute_file_id("content/overview.md")
        b = compute_file_id("content/overview.md")
        assert a == b
        assert len(a) == 12

    def test_compute_file_id_differs_by_path(self):
        assert compute_file_id("a.md") != compute_file_id("b.md")

    def test_derive_doc_title(self):
        assert derive_doc_title("notes.md") == "Notes"
        assert derive_doc_title("api_reference.md") == "Api Reference"
        assert derive_doc_title("kebab-case-doc.md") == "Kebab Case Doc"


class TestNewMetadataFields:
    """Verify Phase 3 metadata is on chunks from all three chunkers."""

    def _assert_phase3_metadata(self, chunk):
        for key in ("doc_title", "file_id", "has_code", "language",
                    "prev_chunk_id", "next_chunk_id"):
            assert key in chunk.metadata, f"missing {key} in {chunk.id}"

    def test_heading_chunker_has_new_metadata(self):
        content = "# Doc\n\n## Section\n\nSome content.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        assert len(chunks) == 1
        self._assert_phase3_metadata(chunks[0])
        assert chunks[0].metadata["doc_title"] == "Doc"

    def test_fixed_chunker_has_new_metadata(self):
        content = "Para one.\n\nPara two.\n\nPara three."
        chunker = FixedChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/no-h1.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        self._assert_phase3_metadata(chunks[0])
        # Falls back to file-stem title when no H1
        assert chunks[0].metadata["doc_title"] == "No H1"

    def test_code_detection_on_heading_chunk(self):
        content = "## Example\n\n```python\nprint('hi')\n```\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        assert chunks[0].metadata["has_code"] is True
        assert chunks[0].metadata["language"] == "python"

    def test_chain_property(self):
        """next_chunk_id of chunk[i] == id of chunk[i+1]."""
        content = "# Doc\n\n## A\n\nA body.\n\n## B\n\nB body.\n\n## C\n\nC body.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        assert chunks[0].metadata["prev_chunk_id"] is None
        assert chunks[-1].metadata["next_chunk_id"] is None
        for i in range(len(chunks) - 1):
            assert chunks[i].metadata["next_chunk_id"] == chunks[i + 1].id
            assert chunks[i + 1].metadata["prev_chunk_id"] == chunks[i].id

    def test_doc_title_shared_across_chunks(self):
        content = "# API Patterns\n\n## A\n\nA body.\n\n## B\n\nB body.\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        titles = {c.metadata["doc_title"] for c in chunks}
        assert titles == {"API Patterns"}
        # Same file_id across chunks of same file
        file_ids = {c.metadata["file_id"] for c in chunks}
        assert len(file_ids) == 1

    def test_heading_chunker_chain_survives_oversized_fallback(self):
        """Chain must be contiguous even when a section falls back to FixedChunker."""
        paras = "\n\n".join(["word " * 80 for _ in range(10)])
        content = f"## Section\n\n{paras}\n"
        chunker = HeadingChunker()
        chunks = chunker.chunk(
            content,
            module_name="test", source_file="content/doc.md",
            tags=[], version="1.0.0", max_tokens=500,
        )
        assert len(chunks) > 1, f"expected multiple chunks, got {len(chunks)}"
        for i in range(len(chunks) - 1):
            assert chunks[i].metadata["next_chunk_id"] == chunks[i + 1].id


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
