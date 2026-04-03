"""Tests for ctx pack — Phase 1: scanner and file classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctx.pack import ScanResult, kebab_case, scan_directory


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_tree(base: Path, files: list[str]) -> None:
    """Create a file tree from a list of relative paths."""
    for rel in files:
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("content")


# ── scan_directory ────────────────────────────────────────────────────────────


class TestScanDirectory:
    def test_classifies_supported_extensions(self, tmp_path):
        make_tree(tmp_path, [
            "spec.pdf", "deck.pptx", "notes.md", "readme.markdown",
            "guide.txt", "page.html", "config.yaml", "data.json",
        ])
        results = scan_directory(tmp_path)
        by_name = {r.source_path.name: r.classification for r in results}

        assert by_name["spec.pdf"] == "pdf"
        assert by_name["deck.pptx"] == "pptx"
        assert by_name["notes.md"] == "markdown"
        assert by_name["readme.markdown"] == "markdown"
        assert by_name["guide.txt"] == "plaintext"
        assert by_name["page.html"] == "html"
        assert by_name["config.yaml"] == "structured"
        assert by_name["data.json"] == "structured"

    def test_unsupported_extensions_included_as_unsupported(self, tmp_path):
        make_tree(tmp_path, ["diagram.png", "archive.zip", "font.ttf"])
        results = scan_directory(tmp_path)
        classes = {r.classification for r in results}
        assert "unsupported" in classes
        assert all(r.classification == "unsupported" for r in results)

    def test_skips_hidden_files(self, tmp_path):
        make_tree(tmp_path, [".hidden.md", "visible.md"])
        results = scan_directory(tmp_path)
        names = [r.source_path.name for r in results]
        assert "visible.md" in names
        assert ".hidden.md" not in names

    def test_skips_hidden_directories(self, tmp_path):
        make_tree(tmp_path, [".git/config.yaml", "docs/guide.md"])
        results = scan_directory(tmp_path)
        names = [r.source_path.name for r in results]
        assert "guide.md" in names
        assert "config.yaml" not in names

    def test_skips_underscore_prefixed(self, tmp_path):
        make_tree(tmp_path, ["_private/notes.md", "public/overview.md"])
        results = scan_directory(tmp_path)
        names = [r.source_path.name for r in results]
        assert "overview.md" in names
        assert "notes.md" not in names

    def test_case_insensitive_extension(self, tmp_path):
        make_tree(tmp_path, ["REPORT.PDF", "SLIDES.PPTX"])
        results = scan_directory(tmp_path)
        classes = {r.classification for r in results}
        assert "pdf" in classes
        assert "pptx" in classes

    def test_returns_sorted_by_path(self, tmp_path):
        make_tree(tmp_path, ["z.md", "a.md", "m.md"])
        results = scan_directory(tmp_path)
        paths = [r.source_path for r in results]
        assert paths == sorted(paths)

    def test_recursive_scan(self, tmp_path):
        make_tree(tmp_path, [
            "top.md",
            "subdir/nested.pdf",
            "subdir/deep/even_deeper.txt",
        ])
        results = scan_directory(tmp_path)
        assert len(results) == 3

    def test_empty_directory_returns_empty(self, tmp_path):
        assert scan_directory(tmp_path) == []

    def test_returns_scan_result_instances(self, tmp_path):
        make_tree(tmp_path, ["doc.md"])
        results = scan_directory(tmp_path)
        assert len(results) == 1
        assert isinstance(results[0], ScanResult)
        assert isinstance(results[0].source_path, Path)

    def test_yml_extension_classified_as_structured(self, tmp_path):
        make_tree(tmp_path, ["config.yml"])
        results = scan_directory(tmp_path)
        assert results[0].classification == "structured"

    def test_htm_extension_classified_as_html(self, tmp_path):
        make_tree(tmp_path, ["page.htm"])
        results = scan_directory(tmp_path)
        assert results[0].classification == "html"

    def test_ppt_extension_classified_as_pptx(self, tmp_path):
        make_tree(tmp_path, ["old.ppt"])
        results = scan_directory(tmp_path)
        assert results[0].classification == "pptx"


# ── kebab_case ────────────────────────────────────────────────────────────────


class TestKebabCase:
    def test_spaces_become_hyphens(self):
        assert kebab_case("API Knowledge Base") == "api-knowledge-base"

    def test_underscores_become_hyphens(self):
        assert kebab_case("v2_api_specs") == "v2-api-specs"

    def test_mixed_spaces_and_underscores(self):
        assert kebab_case("My_API Docs") == "my-api-docs"

    def test_already_kebab(self):
        assert kebab_case("api-patterns") == "api-patterns"

    def test_strips_leading_trailing_whitespace(self):
        assert kebab_case("  hello world  ") == "hello-world"

    def test_collapses_multiple_hyphens(self):
        assert kebab_case("hello--world") == "hello-world"

    def test_lowercases(self):
        assert kebab_case("My Docs") == "my-docs"

    def test_strips_special_characters(self):
        assert kebab_case("API (v2)") == "api-v2"

    def test_numbers_preserved(self):
        assert kebab_case("v2 api specs") == "v2-api-specs"

    def test_single_word(self):
        assert kebab_case("docs") == "docs"

    def test_leading_trailing_hyphens_stripped(self):
        assert kebab_case("-docs-") == "docs"
