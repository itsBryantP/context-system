"""Tests for Box Note (.boxnote) extraction in ctx pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctx.pack import _boxnote_inline_text, _extract_boxnote, scan_directory


# ── Helpers ───────────────────────────────────────────────────────────────────


def write_boxnote(path: Path, content: list) -> None:
    """Write a minimal valid .boxnote file with the given content nodes."""
    path.write_text(json.dumps({
        "version": 1,
        "schema_version": 1,
        "doc": {"type": "doc", "content": content},
    }))


def extract(src: Path, tmp_path: Path) -> str:
    out = tmp_path / (src.stem + ".md")
    _extract_boxnote(src, out)
    return out.read_text()


# ── Scanner classification ────────────────────────────────────────────────────


class TestBoxnoteScanClassification:
    def test_boxnote_classified_correctly(self, tmp_path):
        (tmp_path / "notes.boxnote").write_text("{}")
        results = scan_directory(tmp_path)
        assert results[0].classification == "boxnote"

    def test_ppt_classified_as_unsupported(self, tmp_path):
        (tmp_path / "deck.ppt").write_text("")
        results = scan_directory(tmp_path)
        assert results[0].classification == "unsupported"

    def test_pptx_still_classified_correctly(self, tmp_path):
        (tmp_path / "deck.pptx").write_text("")
        results = scan_directory(tmp_path)
        assert results[0].classification == "pptx"


# ── Empty / minimal documents ────────────────────────────────────────────────


class TestBoxnoteEmpty:
    def test_empty_doc_produces_heading_only(self, tmp_path):
        src = tmp_path / "empty.boxnote"
        write_boxnote(src, [])
        md = extract(src, tmp_path)
        assert md.strip() == "# empty"

    def test_doc_with_only_empty_paragraphs(self, tmp_path):
        src = tmp_path / "blank.boxnote"
        write_boxnote(src, [{"type": "paragraph"}, {"type": "paragraph"}])
        md = extract(src, tmp_path)
        # Should not crash; heading should be present
        assert "# blank" in md

    def test_missing_doc_key(self, tmp_path):
        src = tmp_path / "nodoc.boxnote"
        src.write_text(json.dumps({"version": 1}))
        md = extract(src, tmp_path)
        assert "# nodoc" in md

    def test_invalid_json_raises(self, tmp_path):
        src = tmp_path / "bad.boxnote"
        src.write_text("not json {{{")
        with pytest.raises(RuntimeError, match="parse"):
            extract(src, tmp_path)


# ── Paragraphs ────────────────────────────────────────────────────────────────


class TestBoxnoteParagraphs:
    def test_single_paragraph(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "paragraph", "content": [
            {"type": "text", "text": "Hello world"}
        ]}])
        md = extract(src, tmp_path)
        assert "Hello world" in md

    def test_multiple_paragraphs(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [
            {"type": "paragraph", "content": [{"type": "text", "text": "First"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Second"}]},
        ])
        md = extract(src, tmp_path)
        assert "First" in md
        assert "Second" in md

    def test_consecutive_blank_lines_collapsed(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [
            {"type": "paragraph"},
            {"type": "paragraph"},
            {"type": "paragraph"},
            {"type": "paragraph", "content": [{"type": "text", "text": "Text"}]},
        ])
        md = extract(src, tmp_path)
        assert "\n\n\n" not in md


# ── Headings ─────────────────────────────────────────────────────────────────


class TestBoxnoteHeadings:
    def test_heading_level_2_renders_as_h3(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "heading", "attrs": {"level": 2}, "content": [
            {"type": "text", "text": "Section Title"}
        ]}])
        md = extract(src, tmp_path)
        assert "### Section Title" in md

    def test_heading_level_1_renders_as_h2(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "heading", "attrs": {"level": 1}, "content": [
            {"type": "text", "text": "Top"}
        ]}])
        md = extract(src, tmp_path)
        assert "## Top" in md

    def test_heading_level_3_renders_as_h4(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "heading", "attrs": {"level": 3}, "content": [
            {"type": "text", "text": "Sub"}
        ]}])
        md = extract(src, tmp_path)
        assert "#### Sub" in md

    def test_empty_heading_skipped(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "heading", "attrs": {"level": 2}, "content": []}])
        md = extract(src, tmp_path)
        # No spurious heading marker with no text
        assert "##  " not in md
        assert "### " not in md

    def test_filename_stays_as_h1(self, tmp_path):
        src = tmp_path / "myfile.boxnote"
        write_boxnote(src, [{"type": "heading", "attrs": {"level": 1}, "content": [
            {"type": "text", "text": "Sub"}
        ]}])
        md = extract(src, tmp_path)
        assert md.startswith("# myfile")
        # No second H1
        h1_count = md.count("\n# ")
        assert h1_count == 0  # only the first line is H1


# ── Lists ─────────────────────────────────────────────────────────────────────


class TestBoxnoteLists:
    def test_bullet_list(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "bullet_list", "content": [
            {"type": "list_item", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Item A"}]}
            ]},
            {"type": "list_item", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Item B"}]}
            ]},
        ]}])
        md = extract(src, tmp_path)
        assert "- Item A" in md
        assert "- Item B" in md

    def test_check_list(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "check_list", "content": [
            {"type": "check_list_item", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Task one"}]}
            ]},
        ]}])
        md = extract(src, tmp_path)
        assert "- Task one" in md

    def test_ordered_list(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "ordered_list", "content": [
            {"type": "list_item", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Step one"}]}
            ]},
            {"type": "list_item", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Step two"}]}
            ]},
        ]}])
        md = extract(src, tmp_path)
        assert "1. Step one" in md
        assert "2. Step two" in md

    def test_nested_bullet_list(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "bullet_list", "content": [
            {"type": "list_item", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Parent"}]},
                {"type": "bullet_list", "content": [
                    {"type": "list_item", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Child"}]}
                    ]},
                ]},
            ]},
        ]}])
        md = extract(src, tmp_path)
        assert "- Parent" in md
        assert "- Child" in md
        # Child should be indented relative to parent
        parent_indent = len(md.split("- Parent")[0].rsplit("\n", 1)[-1])
        child_indent = len(md.split("- Child")[0].rsplit("\n", 1)[-1])
        assert child_indent > parent_indent


# ── Inline marks ─────────────────────────────────────────────────────────────


class TestBoxnoteInlineMarks:
    def test_bold_mark(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "paragraph", "content": [
            {"type": "text", "text": "important", "marks": [{"type": "bold"}]}
        ]}])
        md = extract(src, tmp_path)
        assert "**important**" in md

    def test_italic_mark(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "paragraph", "content": [
            {"type": "text", "text": "note", "marks": [{"type": "italic"}]}
        ]}])
        md = extract(src, tmp_path)
        assert "*note*" in md

    def test_code_mark(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "paragraph", "content": [
            {"type": "text", "text": "ctx pack", "marks": [{"type": "code"}]}
        ]}])
        md = extract(src, tmp_path)
        assert "`ctx pack`" in md

    def test_box_metadata_marks_stripped(self, tmp_path):
        """author_id, font_color, font_size marks should not appear in output."""
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "paragraph", "content": [
            {"type": "text", "text": "Clean text", "marks": [
                {"type": "author_id", "attrs": {"authorId": "12345"}},
                {"type": "font_color", "attrs": {"color": "#ff0000"}},
                {"type": "font_size", "attrs": {"size": 14}},
            ]}
        ]}])
        md = extract(src, tmp_path)
        assert "Clean text" in md
        assert "author_id" not in md
        assert "12345" not in md
        assert "font_color" not in md

    def test_mixed_plain_and_bold(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "paragraph", "content": [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world", "marks": [{"type": "bold"}]},
            {"type": "text", "text": "!"},
        ]}])
        md = extract(src, tmp_path)
        assert "Hello **world**!" in md


# ── Horizontal rule ───────────────────────────────────────────────────────────


class TestBoxnoteHorizontalRule:
    def test_horizontal_rule(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [
            {"type": "paragraph", "content": [{"type": "text", "text": "Before"}]},
            {"type": "horizontal_rule"},
            {"type": "paragraph", "content": [{"type": "text", "text": "After"}]},
        ])
        md = extract(src, tmp_path)
        assert "---" in md
        assert "Before" in md
        assert "After" in md


# ── Unknown node types ────────────────────────────────────────────────────────


class TestBoxnoteUnknownNodes:
    def test_unknown_block_type_recurses_into_children(self, tmp_path):
        src = tmp_path / "doc.boxnote"
        write_boxnote(src, [{"type": "some_future_node", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Visible"}]}
        ]}])
        md = extract(src, tmp_path)
        assert "Visible" in md

    def test_session_node_ignored(self, tmp_path):
        """Box Note session metadata nodes should not appear in output."""
        src = tmp_path / "doc.boxnote"
        src.write_text(json.dumps({
            "version": 5,
            "schema_version": 1,
            "doc": {"type": "doc", "content": [
                {"type": "session", "attrs": {"id": "abc"}},
                {"type": "paragraph", "content": [{"type": "text", "text": "Real content"}]},
            ]},
        }))
        md = extract(src, tmp_path)
        assert "Real content" in md
        assert "session" not in md
        assert "abc" not in md


# ── _boxnote_inline_text unit tests ──────────────────────────────────────────


class TestBoxnoteInlineText:
    def test_plain_text(self):
        nodes = [{"type": "text", "text": "hello"}]
        assert _boxnote_inline_text(nodes) == "hello"

    def test_concatenates_multiple_spans(self):
        nodes = [
            {"type": "text", "text": "foo"},
            {"type": "text", "text": " bar"},
        ]
        assert _boxnote_inline_text(nodes) == "foo bar"

    def test_bold(self):
        nodes = [{"type": "text", "text": "x", "marks": [{"type": "bold"}]}]
        assert _boxnote_inline_text(nodes) == "**x**"

    def test_italic(self):
        nodes = [{"type": "text", "text": "x", "marks": [{"type": "italic"}]}]
        assert _boxnote_inline_text(nodes) == "*x*"

    def test_code(self):
        nodes = [{"type": "text", "text": "x", "marks": [{"type": "code"}]}]
        assert _boxnote_inline_text(nodes) == "`x`"

    def test_hard_break(self):
        nodes = [
            {"type": "text", "text": "a"},
            {"type": "hard_break"},
            {"type": "text", "text": "b"},
        ]
        assert _boxnote_inline_text(nodes) == "a\nb"

    def test_empty_list(self):
        assert _boxnote_inline_text([]) == ""

    def test_non_dict_nodes_ignored(self):
        assert _boxnote_inline_text(["garbage", None, 42]) == ""  # type: ignore[arg-type]

    def test_unknown_marks_not_applied(self):
        nodes = [{"type": "text", "text": "plain", "marks": [{"type": "author_id"}]}]
        assert _boxnote_inline_text(nodes) == "plain"


# ── Integration: extract_files picks up .boxnote ──────────────────────────────


class TestBoxnoteExtractFilesIntegration:
    def test_boxnote_included_in_extraction(self, tmp_path):
        from ctx.pack import extract_files, scan_directory

        src = tmp_path / "input"
        src.mkdir()
        note = src / "meeting.boxnote"
        write_boxnote(note, [{"type": "paragraph", "content": [
            {"type": "text", "text": "Meeting notes here"}
        ]}])

        tmp_out = tmp_path / "tmp"
        tmp_out.mkdir()

        results = scan_directory(src)
        extracted, failures = extract_files(results, src, tmp_out)

        assert len(failures) == 0
        assert len(extracted) == 1
        assert extracted[0].classification == "boxnote"
        assert "Meeting notes here" in extracted[0].md_path.read_text()

    def test_ppt_not_included_in_extraction(self, tmp_path):
        from ctx.pack import extract_files, scan_directory

        src = tmp_path / "input"
        src.mkdir()
        (src / "old.ppt").write_bytes(b"\xd0\xcf\x11\xe0")  # OLE2 magic bytes

        tmp_out = tmp_path / "tmp"
        tmp_out.mkdir()

        results = scan_directory(src)
        extracted, failures = extract_files(results, src, tmp_out)

        # .ppt is unsupported — silently skipped, no failures
        assert len(extracted) == 0
        assert len(failures) == 0
