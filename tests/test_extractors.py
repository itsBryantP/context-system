"""Tests for extractor plugins."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ctx.extractors import get_extractor
from ctx.extractors.markdown import MarkdownExtractor, _strip_frontmatter
from ctx.extractors.pdf import PDFExtractor, _plain_text_to_markdown
from ctx.extractors.pptx import PPTXExtractor
from ctx.extractors.url import URLExtractor, _url_to_stem
from ctx.schema import Source, SourceType


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_source(**kwargs) -> Source:
    return Source(**kwargs)


# ── Registry ──────────────────────────────────────────────────────────────────


def test_get_extractor_markdown():
    src = make_source(type=SourceType.MARKDOWN, path="foo.md")
    assert isinstance(get_extractor(src), MarkdownExtractor)


def test_get_extractor_pdf():
    src = make_source(type=SourceType.PDF, path="foo.pdf")
    assert isinstance(get_extractor(src), PDFExtractor)


def test_get_extractor_pptx():
    src = make_source(type=SourceType.PPTX, path="foo.pptx")
    assert isinstance(get_extractor(src), PPTXExtractor)


def test_get_extractor_url():
    src = make_source(type=SourceType.URL, url="https://example.com")
    assert isinstance(get_extractor(src), URLExtractor)


# ── MarkdownExtractor ─────────────────────────────────────────────────────────


class TestMarkdownExtractor:
    def test_copies_plain_markdown(self, tmp_path):
        src_file = tmp_path / "doc.md"
        src_file.write_text("# Hello\n\nWorld.\n")
        out_dir = tmp_path / "out"

        ext = MarkdownExtractor()
        created = ext.extract(
            make_source(type=SourceType.MARKDOWN, path=str(src_file)), out_dir
        )

        assert len(created) == 1
        assert created[0].read_text() == "# Hello\n\nWorld.\n"

    def test_strips_frontmatter(self, tmp_path):
        src_file = tmp_path / "doc.md"
        src_file.write_text("---\ntags: [api]\n---\n\n# Body\n\nContent.\n")
        out_dir = tmp_path / "out"

        ext = MarkdownExtractor()
        created = ext.extract(
            make_source(type=SourceType.MARKDOWN, path=str(src_file)), out_dir
        )

        body = created[0].read_text()
        assert "---" not in body
        assert "# Body" in body

    def test_glob_pattern(self, tmp_path):
        (tmp_path / "a.md").write_text("# A\n")
        (tmp_path / "b.md").write_text("# B\n")
        out_dir = tmp_path / "out"

        ext = MarkdownExtractor()
        created = ext.extract(
            make_source(type=SourceType.MARKDOWN, path=str(tmp_path / "*.md")), out_dir
        )

        assert len(created) == 2

    def test_missing_path_raises(self):
        ext = MarkdownExtractor()
        with pytest.raises(ValueError, match="path"):
            ext.extract(make_source(type=SourceType.MARKDOWN), Path("/tmp"))

    def test_file_not_found_raises(self, tmp_path):
        ext = MarkdownExtractor()
        with pytest.raises(FileNotFoundError):
            ext.extract(
                make_source(type=SourceType.MARKDOWN, path=str(tmp_path / "missing.md")),
                tmp_path / "out",
            )


class TestStripFrontmatter:
    def test_no_frontmatter(self):
        body, tags = _strip_frontmatter("# Hello\n\nWorld.")
        assert body == "# Hello\n\nWorld."
        assert tags == []

    def test_strips_frontmatter_and_extracts_tags(self):
        content = "---\ntitle: Foo\ntags: [api, rest]\n---\n\n# Body\n"
        body, tags = _strip_frontmatter(content)
        assert "---" not in body
        assert "# Body" in body
        assert tags == ["api", "rest"]

    def test_string_tag(self):
        content = "---\ntags: single\n---\n\n# Body\n"
        _, tags = _strip_frontmatter(content)
        assert tags == ["single"]

    def test_incomplete_frontmatter_left_as_is(self):
        content = "---\ntags: [x]\nno closing delimiter"
        body, tags = _strip_frontmatter(content)
        assert body == content
        assert tags == []


# ── PDFExtractor ──────────────────────────────────────────────────────────────


class TestPDFExtractor:
    def test_missing_path_raises(self):
        ext = PDFExtractor()
        with pytest.raises(ValueError, match="path"):
            ext.extract(make_source(type=SourceType.PDF), Path("/tmp"))

    def test_file_not_found_raises(self, tmp_path):
        ext = PDFExtractor()
        with pytest.raises(FileNotFoundError):
            ext.extract(
                make_source(type=SourceType.PDF, path=str(tmp_path / "missing.pdf")),
                tmp_path / "out",
            )

    def test_uses_pdftotext_when_available(self, tmp_path):
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF fake")
        out_dir = tmp_path / "out"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Chapter One\n\nSome text.\n"
            )
            ext = PDFExtractor()
            created = ext.extract(
                make_source(type=SourceType.PDF, path=str(pdf)), out_dir
            )

        assert len(created) == 1
        content = created[0].read_text()
        assert "# report" in content
        assert "Chapter One" in content

    def test_falls_back_to_pymupdf_when_pdftotext_missing(self, tmp_path):
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF fake")
        out_dir = tmp_path / "out"

        # pdftotext not found, pymupdf also unavailable → RuntimeError
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch.dict("sys.modules", {"fitz": None}):
                ext = PDFExtractor()
                with pytest.raises(RuntimeError, match="pdftotext"):
                    ext.extract(
                        make_source(type=SourceType.PDF, path=str(pdf)), out_dir
                    )


class TestPlainTextToMarkdown:
    def test_wraps_in_heading(self):
        md = _plain_text_to_markdown("Hello\n\nWorld", "My Doc")
        assert md.startswith("# My Doc")
        assert "Hello" in md
        assert "World" in md

    def test_collapses_multiple_blanks(self):
        md = _plain_text_to_markdown("A\n\n\n\nB", "doc")
        # should not have more than one consecutive blank line
        assert "\n\n\n" not in md


# ── PPTXExtractor ─────────────────────────────────────────────────────────────


class TestPPTXExtractor:
    def test_missing_path_raises(self):
        ext = PPTXExtractor()
        with pytest.raises(ValueError, match="path"):
            ext.extract(make_source(type=SourceType.PPTX), Path("/tmp"))

    def test_file_not_found_raises(self, tmp_path):
        ext = PPTXExtractor()
        with pytest.raises(FileNotFoundError):
            ext.extract(
                make_source(type=SourceType.PPTX, path=str(tmp_path / "missing.pptx")),
                tmp_path / "out",
            )

    def test_import_error_when_pptx_missing(self, tmp_path):
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"fake")

        with patch.dict("sys.modules", {"pptx": None}):
            ext = PPTXExtractor()
            with pytest.raises((ImportError, Exception)):
                ext.extract(
                    make_source(type=SourceType.PPTX, path=str(pptx_file)),
                    tmp_path / "out",
                )


# ── URLExtractor ──────────────────────────────────────────────────────────────


class TestURLExtractor:
    def test_missing_url_raises(self):
        ext = URLExtractor()
        with pytest.raises(ValueError, match="url"):
            ext.extract(make_source(type=SourceType.URL), Path("/tmp"))

    def test_fetches_and_converts(self, tmp_path):
        with patch("urllib.request.urlopen") as mock_open, \
             patch("ctx.extractors.url._to_markdown", return_value="# Title\n\nBody.\n"):
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b"<html/>"
            mock_resp.headers.get_content_charset.return_value = "utf-8"
            mock_open.return_value = mock_resp

            ext = URLExtractor()
            created = ext.extract(
                make_source(type=SourceType.URL, url="https://example.com/docs"),
                tmp_path,
            )

        assert len(created) == 1
        content = created[0].read_text()
        assert "source_url: https://example.com/docs" in content
        assert "fetched_at:" in content
        assert "# Title" in content

    def test_output_includes_refresh_when_set(self, tmp_path):
        from ctx.schema import RefreshSchedule

        with patch("urllib.request.urlopen") as mock_open, \
             patch("ctx.extractors.url._to_markdown", return_value="content\n"):
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b"<html/>"
            mock_resp.headers.get_content_charset.return_value = "utf-8"
            mock_open.return_value = mock_resp

            ext = URLExtractor()
            created = ext.extract(
                make_source(
                    type=SourceType.URL,
                    url="https://example.com",
                    refresh=RefreshSchedule.WEEKLY,
                ),
                tmp_path,
            )

        assert "refresh: weekly" in created[0].read_text()


class TestUrlToStem:
    def test_derives_stem_from_path(self):
        assert _url_to_stem("https://example.com/docs/api") == "api"

    def test_falls_back_to_netloc(self):
        assert _url_to_stem("https://example.com/") == "example.com"

    def test_sanitises_special_chars(self):
        stem = _url_to_stem("https://example.com/foo.bar?q=1")
        assert "/" not in stem
        assert "?" not in stem
