"""Tests for ctx pack — Phase 1–4: scanner, classification, extraction, strategy, inference."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ctx.pack import (
    ExtractedFile,
    ScanResult,
    build_strategy_map,
    chunk_files,
    extract_files,
    infer_description,
    infer_name,
    infer_tags,
    kebab_case,
    majority_strategy,
    pack,
    scan_directory,
    select_strategy,
    write_module,
)


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


# ── extract_files ─────────────────────────────────────────────────────────────


class TestExtractFiles:
    """Phase 2: extract_files() — one handler per classification."""

    def _scan(self, tmp_path: Path, filenames: list[tuple[str, str]]) -> list[ScanResult]:
        """Build ScanResult list directly without going through scan_directory."""
        results = []
        for name, cls in filenames:
            p = tmp_path / name
            results.append(ScanResult(source_path=p, classification=cls))
        return results

    # ── markdown ──────────────────────────────────────────────────────────────

    def test_markdown_stripped_of_frontmatter(self, tmp_path):
        src = tmp_path / "doc.md"
        src.write_text("---\ntitle: Test\n---\n# Hello\n\nBody text.\n")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, failures = extract_files(
            [ScanResult(source_path=src, classification="markdown")],
            tmp_path,
            tmp_out,
        )
        assert not failures
        assert len(extracted) == 1
        content = extracted[0].md_path.read_text()
        assert "---" not in content
        assert "# Hello" in content

    def test_markdown_no_frontmatter_unchanged(self, tmp_path):
        src = tmp_path / "plain.md"
        src.write_text("# Title\n\nSome content.\n")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, _ = extract_files(
            [ScanResult(source_path=src, classification="markdown")],
            tmp_path,
            tmp_out,
        )
        assert extracted[0].md_path.read_text() == "# Title\n\nSome content.\n"

    # ── plaintext ─────────────────────────────────────────────────────────────

    def test_plaintext_gets_heading(self, tmp_path):
        src = tmp_path / "notes.txt"
        src.write_text("Meeting notes from Monday.\n")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, failures = extract_files(
            [ScanResult(source_path=src, classification="plaintext")],
            tmp_path,
            tmp_out,
        )
        assert not failures
        content = extracted[0].md_path.read_text()
        assert content.startswith("# notes\n")
        assert "Meeting notes from Monday." in content

    # ── structured ────────────────────────────────────────────────────────────

    def test_json_wrapped_in_fenced_block(self, tmp_path):
        src = tmp_path / "config.json"
        src.write_text('{"host": "localhost"}\n')
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, failures = extract_files(
            [ScanResult(source_path=src, classification="structured")],
            tmp_path,
            tmp_out,
        )
        assert not failures
        content = extracted[0].md_path.read_text()
        assert "# config.json" in content
        assert "```json" in content
        assert '"host"' in content

    def test_yaml_wrapped_in_fenced_block(self, tmp_path):
        src = tmp_path / "settings.yaml"
        src.write_text("key: value\n")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, _ = extract_files(
            [ScanResult(source_path=src, classification="structured")],
            tmp_path,
            tmp_out,
        )
        content = extracted[0].md_path.read_text()
        assert "# settings.yaml" in content
        assert "```yaml" in content
        assert "key: value" in content

    def test_yml_extension_uses_yaml_fence(self, tmp_path):
        src = tmp_path / "cfg.yml"
        src.write_text("a: 1\n")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, _ = extract_files(
            [ScanResult(source_path=src, classification="structured")],
            tmp_path,
            tmp_out,
        )
        assert "```yaml" in extracted[0].md_path.read_text()

    # ── html ──────────────────────────────────────────────────────────────────

    def test_html_converted_with_markdownify(self, tmp_path):
        src = tmp_path / "page.html"
        src.write_text("<h1>Title</h1><p>Body</p>")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        markdownify = pytest.importorskip("markdownify")
        extracted, failures = extract_files(
            [ScanResult(source_path=src, classification="html")],
            tmp_path,
            tmp_out,
        )
        assert not failures
        content = extracted[0].md_path.read_text()
        assert "Title" in content
        assert "Body" in content

    def test_html_fails_gracefully_without_markdownify(self, tmp_path):
        src = tmp_path / "page.html"
        src.write_text("<h1>Hi</h1>")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        with patch.dict("sys.modules", {"markdownify": None}):
            extracted, failures = extract_files(
                [ScanResult(source_path=src, classification="html")],
                tmp_path,
                tmp_out,
            )
        assert not extracted
        assert len(failures) == 1
        assert failures[0][0] == src

    # ── pdf / pptx — mock the internals ──────────────────────────────────────

    def test_pdf_extraction_uses_internal_helpers(self, tmp_path):
        src = tmp_path / "doc.pdf"
        src.write_text("fake pdf")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        with (
            patch("ctx.extractors.pdf._extract_pdftotext", return_value="# doc\n\nExtracted.\n"),
            patch("ctx.extractors.pdf._extract_pymupdf", return_value=None),
        ):
            extracted, failures = extract_files(
                [ScanResult(source_path=src, classification="pdf")],
                tmp_path,
                tmp_out,
            )
        assert not failures
        assert "Extracted." in extracted[0].md_path.read_text()

    def test_pdf_failure_when_no_extractor_available(self, tmp_path):
        src = tmp_path / "broken.pdf"
        src.write_text("fake pdf")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        with (
            patch("ctx.extractors.pdf._extract_pdftotext", return_value=None),
            patch("ctx.extractors.pdf._extract_pymupdf", return_value=None),
        ):
            extracted, failures = extract_files(
                [ScanResult(source_path=src, classification="pdf")],
                tmp_path,
                tmp_out,
            )
        assert not extracted
        assert len(failures) == 1

    def test_pptx_extraction_uses_internal_helper(self, tmp_path):
        src = tmp_path / "slides.pptx"
        src.write_text("fake pptx")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        with patch("ctx.extractors.pptx._extract_pptx", return_value="# slides\n\n## Slide 1\n"):
            extracted, failures = extract_files(
                [ScanResult(source_path=src, classification="pptx")],
                tmp_path,
                tmp_out,
            )
        assert not failures
        assert "## Slide 1" in extracted[0].md_path.read_text()

    # ── unsupported files are skipped ─────────────────────────────────────────

    def test_unsupported_files_are_skipped(self, tmp_path):
        src = tmp_path / "image.png"
        src.write_text("fake")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, failures = extract_files(
            [ScanResult(source_path=src, classification="unsupported")],
            tmp_path,
            tmp_out,
        )
        assert not extracted
        assert not failures  # silently skipped, not a failure

    # ── failure isolation ─────────────────────────────────────────────────────

    def test_failure_does_not_abort_remaining_files(self, tmp_path):
        good = tmp_path / "good.md"
        good.write_text("# Good\n")
        bad = tmp_path / "bad.pdf"
        bad.write_text("fake")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        with (
            patch("ctx.extractors.pdf._extract_pdftotext", return_value=None),
            patch("ctx.extractors.pdf._extract_pymupdf", return_value=None),
        ):
            extracted, failures = extract_files(
                [
                    ScanResult(source_path=good, classification="markdown"),
                    ScanResult(source_path=bad, classification="pdf"),
                ],
                tmp_path,
                tmp_out,
            )
        assert len(extracted) == 1
        assert extracted[0].original_path == good
        assert len(failures) == 1
        assert failures[0][0] == bad

    # ── ExtractedFile dataclass ───────────────────────────────────────────────

    def test_extracted_file_has_correct_fields(self, tmp_path):
        src = tmp_path / "readme.md"
        src.write_text("# Hi\n")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, _ = extract_files(
            [ScanResult(source_path=src, classification="markdown")],
            tmp_path,
            tmp_out,
        )
        ef = extracted[0]
        assert isinstance(ef, ExtractedFile)
        assert ef.original_path == src
        assert ef.md_path.suffix == ".md"
        assert ef.classification == "markdown"

    # ── collision avoidance ───────────────────────────────────────────────────

    def test_files_with_same_name_in_different_subdirs(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        f1 = tmp_path / "a" / "notes.md"
        f2 = tmp_path / "b" / "notes.md"
        f1.write_text("# A\n")
        f2.write_text("# B\n")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        extracted, failures = extract_files(
            [
                ScanResult(source_path=f1, classification="markdown"),
                ScanResult(source_path=f2, classification="markdown"),
            ],
            tmp_path,
            tmp_out,
        )
        assert not failures
        assert len(extracted) == 2
        # Both outputs should be distinct paths
        assert extracted[0].md_path != extracted[1].md_path


# ── select_strategy ───────────────────────────────────────────────────────────


class TestSelectStrategy:
    """Phase 3: strategy heuristic."""

    from ctx.schema import ChunkingStrategy

    # ── token shortcut ────────────────────────────────────────────────────────

    def test_tiny_document_returns_fixed(self):
        from ctx.schema import ChunkingStrategy
        # A very short document fits within max_tokens → FIXED regardless of headings
        content = "## Hello\n\nShort.\n"
        assert select_strategy(content, max_tokens=10_000) == ChunkingStrategy.FIXED

    # ── DEFINITION via bold defs ──────────────────────────────────────────────

    def test_bold_defs_trigger_definition(self):
        from ctx.schema import ChunkingStrategy
        # 3 bold-definition patterns, no H2 headings → DEFINITION
        block = "word " * 600  # enough tokens
        content = (
            block
            + "**API**: Application Programming Interface.\n"
            + "**SDK**: Software Development Kit.\n"
            + "**CLI**: Command-Line Interface.\n"
        )
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.DEFINITION

    def test_bold_defs_must_outnumber_h2_headings(self):
        from ctx.schema import ChunkingStrategy
        # 3 bold defs but 4 H2 headings → bold_defs NOT > headings_h2 → falls through
        block = "word " * 600
        content = (
            block
            + "## Section One\n## Section Two\n## Section Three\n## Section Four\n"
            + "**API**: A.\n**SDK**: B.\n**CLI**: C.\n"
        )
        # bold_defs (3) is NOT > headings_h2 (4), so falls to HEADING (>=2 H2)
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.HEADING

    # ── DEFINITION via H3/H4 density ─────────────────────────────────────────

    def test_h3h4_density_triggers_definition(self):
        from ctx.schema import ChunkingStrategy
        block = "word " * 600
        # 1 H2, 6 H3 → headings_h3h4 (6) > headings_h2 (1) * 2 → DEFINITION
        content = (
            block
            + "## Overview\n"
            + "### Alpha\n### Beta\n### Gamma\n### Delta\n### Epsilon\n### Zeta\n"
        )
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.DEFINITION

    def test_h3h4_must_exceed_double_h2(self):
        from ctx.schema import ChunkingStrategy
        block = "word " * 600
        # 3 H2, 4 H3 → 4 is NOT > 3*2=6 → falls to HEADING
        content = (
            block
            + "## A\n## B\n## C\n"
            + "### X\n### Y\n### Z\n### W\n"
        )
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.HEADING

    # ── HEADING ───────────────────────────────────────────────────────────────

    def test_two_h2_headings_returns_heading(self):
        from ctx.schema import ChunkingStrategy
        block = "word\n" * 400
        content = block + "## Section One\n\nContent.\n\n## Section Two\n\nContent.\n"
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.HEADING

    def test_single_h2_returns_fixed(self):
        from ctx.schema import ChunkingStrategy
        block = "word " * 600
        content = block + "## Only One Section\n\nContent.\n"
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.FIXED

    # ── FIXED fallback ────────────────────────────────────────────────────────

    def test_no_structure_returns_fixed(self):
        from ctx.schema import ChunkingStrategy
        content = "word " * 600  # lots of tokens, no headings, no bold defs
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.FIXED

    # ── em-dash and en-dash variants ──────────────────────────────────────────

    def test_bold_def_with_em_dash(self):
        from ctx.schema import ChunkingStrategy
        block = "word " * 600
        content = (
            block
            + "**Alpha** \u2014 first Greek letter.\n"
            + "**Beta** \u2014 second Greek letter.\n"
            + "**Gamma** \u2014 third Greek letter.\n"
        )
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.DEFINITION

    def test_bold_def_with_en_dash(self):
        from ctx.schema import ChunkingStrategy
        block = "word " * 600
        content = (
            block
            + "**Alpha** \u2013 first.\n"
            + "**Beta** \u2013 second.\n"
            + "**Gamma** \u2013 third.\n"
        )
        assert select_strategy(content, max_tokens=500) == ChunkingStrategy.DEFINITION


# ── build_strategy_map ────────────────────────────────────────────────────────


class TestBuildStrategyMap:
    def _make_ef(self, tmp_path: Path, name: str, content: str) -> ExtractedFile:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return ExtractedFile(original_path=p, md_path=p, classification="markdown")

    def test_returns_strategy_for_each_file(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_ef(tmp_path, "a.md", "# Hi\n\n" + "word " * 600)
        result = build_strategy_map([ef], max_tokens=500)
        assert ef.md_path in result
        assert isinstance(result[ef.md_path], ChunkingStrategy)

    def test_override_forces_same_strategy_for_all(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef1 = self._make_ef(tmp_path, "a.md", "word " * 600 + "## A\n## B\n")
        ef2 = self._make_ef(tmp_path, "b.md", "word " * 600 + "**X**: y.\n**P**: q.\n**Z**: r.\n")
        result = build_strategy_map([ef1, ef2], max_tokens=500, override=ChunkingStrategy.FIXED)
        assert result[ef1.md_path] == ChunkingStrategy.FIXED
        assert result[ef2.md_path] == ChunkingStrategy.FIXED

    def test_empty_list_returns_empty_map(self, tmp_path):
        assert build_strategy_map([]) == {}


# ── infer_name ────────────────────────────────────────────────────────────────


class TestInferName:
    def test_uses_override_when_given(self, tmp_path):
        assert infer_name(tmp_path, override="My Module") == "my-module"

    def test_override_is_kebab_cased(self, tmp_path):
        assert infer_name(tmp_path, override="API Knowledge Base") == "api-knowledge-base"

    def test_falls_back_to_dir_name(self, tmp_path):
        d = tmp_path / "my_api_docs"
        d.mkdir()
        assert infer_name(d) == "my-api-docs"

    def test_dir_name_with_spaces(self, tmp_path):
        d = tmp_path / "API Docs"
        d.mkdir()
        assert infer_name(d) == "api-docs"

    def test_none_override_uses_dir(self, tmp_path):
        d = tmp_path / "runbooks"
        d.mkdir()
        assert infer_name(d, override=None) == "runbooks"


# ── infer_description ─────────────────────────────────────────────────────────


class TestInferDescription:
    def test_returns_first_h1(self):
        contents = ["# API Reference\n\nSome body.\n"]
        assert infer_description(contents, "api-docs") == "API Reference"

    def test_strips_whitespace_from_h1(self):
        contents = ["#  Spaced Heading  \n"]
        assert infer_description(contents, "x") == "Spaced Heading"

    def test_uses_first_h1_across_multiple_docs(self):
        contents = [
            "No heading here.\n",
            "# Second Doc Title\n\nBody.\n",
            "# Third Doc\n",
        ]
        assert infer_description(contents, "x") == "Second Doc Title"

    def test_fallback_when_no_h1(self):
        contents = ["## Section\n\nContent without H1.\n"]
        assert infer_description(contents, "my-dir") == "Context module packed from my-dir"

    def test_fallback_on_empty_contents(self):
        assert infer_description([], "my-dir") == "Context module packed from my-dir"

    def test_h2_does_not_count_as_h1(self):
        contents = ["## Not An H1\n\n# Actual H1\n"]
        assert infer_description(contents, "x") == "Actual H1"


# ── infer_tags ────────────────────────────────────────────────────────────────


class TestInferTags:
    def test_override_splits_on_commas(self):
        assert infer_tags([], override="api,rest,auth") == ["api", "rest", "auth"]

    def test_override_strips_whitespace(self):
        assert infer_tags([], override=" api , rest ") == ["api", "rest"]

    def test_override_empty_string_returns_empty(self):
        assert infer_tags([], override="") == []

    def test_terms_in_two_docs_are_included(self):
        docs = [
            "## Authentication\n\n**token**: A secret value.\n",
            "## Authentication\n\nUse **token** to access.\n",
        ]
        tags = infer_tags(docs)
        assert "authentication" in tags
        assert "token" in tags

    def test_terms_in_one_doc_are_excluded(self):
        docs = [
            "## Authentication\n\n**token**: a secret.\n",
            "## Deployment\n\nSome content.\n",
        ]
        tags = infer_tags(docs)
        # "deployment" appears only in doc 2, "token" only in doc 1
        assert "deployment" not in tags
        assert "token" not in tags

    def test_stop_words_excluded(self):
        docs = [
            "## The API\n## The Guide\n",
            "## The API\n## The Guide\n",
        ]
        tags = infer_tags(docs)
        assert "the" not in tags

    def test_short_words_excluded(self):
        docs = [
            "## an API\n",
            "## an API\n",
        ]
        tags = infer_tags(docs)
        assert "an" not in tags

    def test_returns_at_most_five_tags(self):
        # 8 terms appearing in both docs → should be capped at 5
        heading = "## alpha beta gamma delta epsilon zeta eta theta\n"
        docs = [heading, heading]
        tags = infer_tags(docs)
        assert len(tags) <= 5

    def test_returns_empty_when_fewer_than_two_qualify(self):
        # Only one term appears in 2+ docs
        docs = [
            "## authentication\n",
            "## authentication\n",
        ]
        tags = infer_tags(docs)
        # Only 1 qualifying term → returns []
        assert tags == []

    def test_returns_empty_for_no_content(self):
        assert infer_tags([]) == []

    def test_bold_terms_in_headings_are_counted(self):
        docs = [
            "# Guide\n\n**REST** is a style. **API** design matters.\n",
            "# Reference\n\n**REST** APIs are common. **API** guide here.\n",
        ]
        tags = infer_tags(docs)
        assert "rest" in tags
        assert "api" in tags

    def test_h1_through_h3_headings_scanned(self):
        docs = [
            "# Overview\n## Details\n### Specifics\n",
            "# Overview\n## Details\n### Specifics\n",
        ]
        tags = infer_tags(docs)
        assert "overview" in tags
        assert "details" in tags
        assert "specifics" in tags

    def test_h4_headings_not_scanned(self):
        docs = [
            "#### OnlyH4\n",
            "#### OnlyH4\n",
        ]
        tags = infer_tags(docs)
        assert "onlyh4" not in tags


# ── chunk_files ───────────────────────────────────────────────────────────────


class TestChunkFiles:
    def _make_ef(self, tmp_path: Path, name: str, content: str, cls: str = "markdown") -> ExtractedFile:
        orig = tmp_path / name
        orig.write_text(content)
        md = tmp_path / (name + ".md")
        md.write_text(content)
        return ExtractedFile(original_path=orig, md_path=md, classification=cls)

    def test_returns_chunks_for_each_file(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_ef(tmp_path, "doc.md", "# Title\n\nSome content paragraph here.\n")
        strategies = {ef.md_path: ChunkingStrategy.HEADING}
        chunks = chunk_files([ef], strategies, "my-module", [], input_dir=tmp_path)
        assert len(chunks) >= 1

    def test_source_file_is_relative_to_input_dir(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        sub = tmp_path / "sub"
        sub.mkdir()
        orig = sub / "notes.txt"
        orig.write_text("Some text.")
        md = tmp_path / "notes.txt.md"
        md.write_text("# notes\n\nSome text.")
        ef = ExtractedFile(original_path=orig, md_path=md, classification="plaintext")
        strategies = {ef.md_path: ChunkingStrategy.FIXED}
        chunks = chunk_files([ef], strategies, "mod", [], input_dir=tmp_path)
        assert all(c.source_file == "sub/notes.txt" for c in chunks)

    def test_source_file_falls_back_to_name_when_no_input_dir(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_ef(tmp_path, "spec.pdf", "# Spec\n\nBody.")
        strategies = {ef.md_path: ChunkingStrategy.FIXED}
        chunks = chunk_files([ef], strategies, "mod", [], input_dir=None)
        assert all(c.source_file == "spec.pdf" for c in chunks)

    def test_tags_propagated_to_chunks(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_ef(tmp_path, "guide.md", "# Guide\n\nContent here.")
        strategies = {ef.md_path: ChunkingStrategy.FIXED}
        chunks = chunk_files([ef], strategies, "mod", ["api", "rest"], input_dir=tmp_path)
        for c in chunks:
            assert "api" in c.metadata.get("tags", [])

    def test_module_name_in_chunk_id(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_ef(tmp_path, "overview.md", "# Overview\n\nBody.")
        strategies = {ef.md_path: ChunkingStrategy.HEADING}
        chunks = chunk_files([ef], strategies, "my-module", [], input_dir=tmp_path)
        assert all(c.id.startswith("my-module/") for c in chunks)

    def test_empty_extracted_files_returns_empty(self, tmp_path):
        chunks = chunk_files([], {}, "mod", [], input_dir=tmp_path)
        assert chunks == []

    def test_definition_strategy_used_for_glossary(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        content = "# Glossary\n\n**API**: Application interface.\n\n**SDK**: Dev kit.\n"
        ef = self._make_ef(tmp_path, "glossary.md", content)
        strategies = {ef.md_path: ChunkingStrategy.DEFINITION}
        chunks = chunk_files([ef], strategies, "mod", [], input_dir=tmp_path)
        assert len(chunks) >= 1


# ── majority_strategy ─────────────────────────────────────────────────────────


class TestMajorityStrategy:
    def test_returns_most_common(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
        strategies = {
            a: ChunkingStrategy.HEADING,
            b: ChunkingStrategy.HEADING,
            c: ChunkingStrategy.FIXED,
        }
        assert majority_strategy(strategies) == ChunkingStrategy.HEADING

    def test_empty_returns_heading(self):
        from ctx.schema import ChunkingStrategy
        assert majority_strategy({}) == ChunkingStrategy.HEADING

    def test_single_entry(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        strategies = {tmp_path / "a": ChunkingStrategy.DEFINITION}
        assert majority_strategy(strategies) == ChunkingStrategy.DEFINITION


# ── write_module ──────────────────────────────────────────────────────────────


class TestWriteModule:
    def _make_extracted(self, tmp_path: Path, name: str, content: str, cls: str = "markdown") -> ExtractedFile:
        orig = tmp_path / "src" / name
        orig.parent.mkdir(exist_ok=True)
        orig.write_text(content)
        md = tmp_path / "tmp" / (name + ".extracted.md")
        md.parent.mkdir(exist_ok=True)
        md.write_text(content)
        return ExtractedFile(original_path=orig, md_path=md, classification=cls)

    def _make_chunks(self, extracted, strategies, module_name="mod", tmp_path=None):
        src_dir = tmp_path / "src" if tmp_path else Path(".")
        return chunk_files(extracted, strategies, module_name, [], input_dir=src_dir)

    def test_creates_module_yaml(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_extracted(tmp_path, "doc.md", "# Doc\n\nBody.", "markdown")
        strategies = {ef.md_path: ChunkingStrategy.HEADING}
        chunks = self._make_chunks([ef], strategies, tmp_path=tmp_path)
        out = tmp_path / "output"
        write_module(out, "my-mod", "A module", [], [ef], strategies, chunks, 500, 50)
        assert (out / "module.yaml").exists()

    def test_creates_content_dir_with_md_files(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_extracted(tmp_path, "guide.md", "# Guide\n\nContent.", "markdown")
        strategies = {ef.md_path: ChunkingStrategy.HEADING}
        chunks = self._make_chunks([ef], strategies, tmp_path=tmp_path)
        out = tmp_path / "output"
        write_module(out, "mod", "desc", [], [ef], strategies, chunks, 500, 50)
        assert (out / "content").is_dir()
        assert len(list((out / "content").glob("*.md"))) == 1

    def test_creates_chunks_jsonl(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        ef = self._make_extracted(tmp_path, "api.md", "# API\n\nEndpoints.", "markdown")
        strategies = {ef.md_path: ChunkingStrategy.HEADING}
        chunks = self._make_chunks([ef], strategies, module_name="my-api", tmp_path=tmp_path)
        out = tmp_path / "output"
        write_module(out, "my-api", "desc", [], [ef], strategies, chunks, 500, 50)
        jsonl_path = out / "chunks" / "my-api.jsonl"
        assert jsonl_path.exists()

    def test_module_yaml_has_correct_name_and_description(self, tmp_path):
        import yaml as _yaml
        from ctx.schema import ChunkingStrategy
        ef = self._make_extracted(tmp_path, "doc.md", "# Doc\n\nBody.", "markdown")
        strategies = {ef.md_path: ChunkingStrategy.HEADING}
        chunks = self._make_chunks([ef], strategies, tmp_path=tmp_path)
        out = tmp_path / "output"
        write_module(out, "test-mod", "My description", ["api"], [ef], strategies, chunks, 500, 50)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["name"] == "test-mod"
        assert data["description"] == "My description"
        assert data["tags"] == ["api"]

    def test_module_yaml_majority_strategy(self, tmp_path):
        import yaml as _yaml
        from ctx.schema import ChunkingStrategy
        ef1 = self._make_extracted(tmp_path, "a.md", "# A\n\nBody.", "markdown")
        ef2 = self._make_extracted(tmp_path, "b.md", "# B\n\nBody.", "markdown")
        ef3 = self._make_extracted(tmp_path, "c.md", "# C\n\nBody.", "markdown")
        strategies = {
            ef1.md_path: ChunkingStrategy.HEADING,
            ef2.md_path: ChunkingStrategy.HEADING,
            ef3.md_path: ChunkingStrategy.FIXED,
        }
        chunks = self._make_chunks([ef1, ef2, ef3], strategies, tmp_path=tmp_path)
        out = tmp_path / "output"
        write_module(out, "mod", "desc", [], [ef1, ef2, ef3], strategies, chunks, 500, 50)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["chunking"]["strategy"] == "heading"

    def test_module_yaml_overrides_for_minority_strategy(self, tmp_path):
        import yaml as _yaml
        from ctx.schema import ChunkingStrategy
        ef1 = self._make_extracted(tmp_path, "a.md", "# A\n\nBody.", "markdown")
        ef2 = self._make_extracted(tmp_path, "b.md", "# B\n\nBody.", "markdown")
        strategies = {
            ef1.md_path: ChunkingStrategy.HEADING,
            ef2.md_path: ChunkingStrategy.FIXED,
        }
        chunks = self._make_chunks([ef1, ef2], strategies, tmp_path=tmp_path)
        out = tmp_path / "output"
        write_module(out, "mod", "desc", [], [ef1, ef2], strategies, chunks, 500, 50)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        overrides = data["chunking"].get("overrides", [])
        assert len(overrides) >= 1

    def test_raises_if_output_path_exists(self, tmp_path):
        from ctx.schema import ChunkingStrategy
        out = tmp_path / "output"
        out.mkdir()
        ef = self._make_extracted(tmp_path, "doc.md", "# D\n\nB.", "markdown")
        strategies = {ef.md_path: ChunkingStrategy.HEADING}
        chunks = self._make_chunks([ef], strategies, tmp_path=tmp_path)
        with pytest.raises(FileExistsError):
            write_module(out, "mod", "desc", [], [ef], strategies, chunks, 500, 50)

    def test_sources_list_populated(self, tmp_path):
        import yaml as _yaml
        from ctx.schema import ChunkingStrategy
        ef_md = self._make_extracted(tmp_path, "guide.md", "# G\n\nB.", "markdown")
        ef_pdf = self._make_extracted(tmp_path, "spec.pdf", "# S\n\nB.", "pdf")
        strategies = {
            ef_md.md_path: ChunkingStrategy.HEADING,
            ef_pdf.md_path: ChunkingStrategy.HEADING,
        }
        chunks = self._make_chunks([ef_md, ef_pdf], strategies, tmp_path=tmp_path)
        out = tmp_path / "output"
        write_module(out, "mod", "desc", [], [ef_md, ef_pdf], strategies, chunks, 500, 50)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        source_types = {s["type"] for s in data.get("sources", [])}
        assert "pdf" in source_types
        assert "markdown" in source_types


# ── pack orchestrator ─────────────────────────────────────────────────────────


class TestPack:
    def _setup_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "input"
        d.mkdir()
        (d / "overview.md").write_text("# Overview\n\nSome content about APIs.\n\n## Authentication\n\nUse tokens.\n")
        (d / "notes.txt").write_text("Plain text meeting notes here.\n")
        (d / "config.json").write_text('{"host": "localhost"}\n')
        return d

    def test_stdout_mode_produces_jsonl(self, tmp_path, capsys):
        d = self._setup_dir(tmp_path)
        chunks = pack(d, fmt="jsonl")
        captured = capsys.readouterr()
        assert len(chunks) >= 1
        # Each stdout line is valid JSON
        lines = [l for l in captured.out.strip().splitlines() if l.strip()]
        import json
        for line in lines:
            obj = json.loads(line)
            assert "id" in obj
            assert "content" in obj

    def test_stdout_mode_text_format(self, tmp_path, capsys):
        d = self._setup_dir(tmp_path)
        pack(d, fmt="text")
        captured = capsys.readouterr()
        assert "---" in captured.out
        assert "tokens" in captured.out

    def test_output_mode_creates_module_dir(self, tmp_path):
        d = self._setup_dir(tmp_path)
        out = tmp_path / "my-module"
        pack(d, output=out)
        assert (out / "module.yaml").exists()
        assert (out / "content").is_dir()
        assert list((out / "chunks").glob("*.jsonl"))

    def test_output_mode_auto_detects_name_from_dir(self, tmp_path):
        import yaml as _yaml
        d = tmp_path / "api_reference"
        d.mkdir()
        (d / "guide.md").write_text("# Guide\n\nContent.\n")
        (d / "index.md").write_text("# Index\n\nContent.\n")
        out = tmp_path / "output"
        pack(d, output=out)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["name"] == "api-reference"

    def test_output_mode_name_override(self, tmp_path):
        import yaml as _yaml
        d = self._setup_dir(tmp_path)
        out = tmp_path / "output"
        pack(d, name="custom-name", output=out)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["name"] == "custom-name"

    def test_output_mode_description_override(self, tmp_path):
        import yaml as _yaml
        d = self._setup_dir(tmp_path)
        out = tmp_path / "output"
        pack(d, description="My custom description", output=out)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["description"] == "My custom description"

    def test_output_mode_tags_override(self, tmp_path):
        import yaml as _yaml
        d = self._setup_dir(tmp_path)
        out = tmp_path / "output"
        pack(d, tags="api,auth,rest", output=out)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["tags"] == ["api", "auth", "rest"]

    def test_strategy_override_forces_all_files(self, tmp_path):
        import yaml as _yaml
        d = self._setup_dir(tmp_path)
        out = tmp_path / "output"
        pack(d, strategy="fixed", output=out)
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["chunking"]["strategy"] == "fixed"

    def test_empty_dir_returns_no_chunks(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        chunks = pack(d)
        assert chunks == []

    def test_unsupported_only_dir_returns_no_chunks(self, tmp_path):
        d = tmp_path / "images"
        d.mkdir()
        (d / "photo.png").write_text("fake")
        (d / "diagram.svg").write_text("fake")
        chunks = pack(d)
        assert chunks == []

    def test_install_mode_writes_to_packed_dir(self, tmp_path):
        d = self._setup_dir(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        pack(d, install=True, project_root=project)
        packed_base = project / ".context" / "packed"
        assert packed_base.is_dir()
        subdirs = list(packed_base.iterdir())
        assert len(subdirs) == 1
        assert (subdirs[0] / "module.yaml").exists()

    def test_install_mode_adds_to_config_yaml(self, tmp_path):
        import yaml as _yaml
        d = self._setup_dir(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        pack(d, install=True, project_root=project)
        config_path = project / ".context" / "config.yaml"
        assert config_path.exists()
        data = _yaml.safe_load(config_path.read_text())
        assert any(m.get("path") for m in data.get("modules", []))


# ── CLI integration ───────────────────────────────────────────────────────────


class TestPackCLI:
    def test_cli_stdout_jsonl(self, tmp_path):
        import json
        from click.testing import CliRunner
        from ctx.cli import cli

        d = tmp_path / "input"
        d.mkdir()
        (d / "readme.md").write_text("# Readme\n\nContent.\n")

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["pack", str(d)])
        assert result.exit_code == 0, result.output
        lines = [l for l in result.output.strip().splitlines() if l.strip()]
        assert lines
        obj = json.loads(lines[0])
        assert "id" in obj

    def test_cli_output_flag(self, tmp_path):
        from click.testing import CliRunner
        from ctx.cli import cli

        d = tmp_path / "input"
        d.mkdir()
        (d / "guide.md").write_text("# Guide\n\nContent.\n")
        out = tmp_path / "module-out"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["pack", str(d), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert (out / "module.yaml").exists()

    def test_cli_text_format(self, tmp_path):
        from click.testing import CliRunner
        from ctx.cli import cli

        d = tmp_path / "input"
        d.mkdir()
        (d / "doc.md").write_text("# Doc\n\nSome content here.\n")

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["pack", str(d), "-f", "text"])
        assert result.exit_code == 0, result.output
        assert "---" in result.output

    def test_cli_name_and_description_flags(self, tmp_path):
        import yaml as _yaml
        from click.testing import CliRunner
        from ctx.cli import cli

        d = tmp_path / "input"
        d.mkdir()
        (d / "doc.md").write_text("# Doc\n\nContent.\n")
        out = tmp_path / "output"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, [
            "pack", str(d), "-o", str(out),
            "-n", "my-module", "-d", "Custom description",
        ])
        assert result.exit_code == 0, result.output
        data = _yaml.safe_load((out / "module.yaml").read_text())
        assert data["name"] == "my-module"
        assert data["description"] == "Custom description"
