"""Tests for build metadata and freshness tracking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctx.freshness import (
    compute_module_hash,
    is_fresh,
    load_build_meta,
    record_build,
    save_build_meta,
)


def make_module(base: Path, files: dict[str, str] | None = None) -> Path:
    mod = base / "my-module"
    content_dir = mod / "content"
    content_dir.mkdir(parents=True)
    for name, body in (files or {"overview.md": "# Hello\n"}).items():
        (content_dir / name).write_text(body)
    return mod


class TestComputeModuleHash:
    def test_returns_hex_string(self, tmp_path):
        mod = make_module(tmp_path)
        h = compute_module_hash(mod)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_same_content_same_hash(self, tmp_path):
        mod = make_module(tmp_path)
        assert compute_module_hash(mod) == compute_module_hash(mod)

    def test_changed_content_changes_hash(self, tmp_path):
        mod = make_module(tmp_path)
        h1 = compute_module_hash(mod)
        (mod / "content" / "overview.md").write_text("# Changed\n")
        h2 = compute_module_hash(mod)
        assert h1 != h2

    def test_added_file_changes_hash(self, tmp_path):
        mod = make_module(tmp_path)
        h1 = compute_module_hash(mod)
        (mod / "content" / "new.md").write_text("# New\n")
        h2 = compute_module_hash(mod)
        assert h1 != h2

    def test_missing_content_dir_returns_empty(self, tmp_path):
        mod = tmp_path / "empty"
        mod.mkdir()
        assert compute_module_hash(mod) == ""


class TestBuildMeta:
    def test_load_missing_returns_empty(self, tmp_path):
        assert load_build_meta(tmp_path) == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        meta = {"modules": {"my-mod": {"source_hash": "abc", "chunk_count": 5}}}
        save_build_meta(tmp_path, meta)
        loaded = load_build_meta(tmp_path)
        assert loaded == meta

    def test_corrupt_meta_returns_empty(self, tmp_path):
        path = tmp_path / ".context" / ".build-meta.json"
        path.parent.mkdir(parents=True)
        path.write_text("not json{{")
        assert load_build_meta(tmp_path) == {}


class TestIsFresh:
    def test_matching_hash_is_fresh(self):
        meta = {"modules": {"mod": {"source_hash": "abc123"}}}
        assert is_fresh("mod", "abc123", meta) is True

    def test_different_hash_not_fresh(self):
        meta = {"modules": {"mod": {"source_hash": "abc123"}}}
        assert is_fresh("mod", "xyz999", meta) is False

    def test_missing_module_not_fresh(self):
        assert is_fresh("unknown", "abc123", {}) is False

    def test_empty_hash_not_fresh(self):
        meta = {"modules": {"mod": {"source_hash": ""}}}
        assert is_fresh("mod", "", meta) is False


class TestRecordBuild:
    def test_records_hash_and_count(self, tmp_path):
        record_build(tmp_path, "my-mod", "deadbeef", 42)
        meta = load_build_meta(tmp_path)
        entry = meta["modules"]["my-mod"]
        assert entry["source_hash"] == "deadbeef"
        assert entry["chunk_count"] == 42
        assert "built_at" in entry

    def test_overwrites_previous_entry(self, tmp_path):
        record_build(tmp_path, "my-mod", "hash1", 10)
        record_build(tmp_path, "my-mod", "hash2", 20)
        meta = load_build_meta(tmp_path)
        assert meta["modules"]["my-mod"]["source_hash"] == "hash2"

    def test_multiple_modules_coexist(self, tmp_path):
        record_build(tmp_path, "mod-a", "aaa", 1)
        record_build(tmp_path, "mod-b", "bbb", 2)
        meta = load_build_meta(tmp_path)
        assert "mod-a" in meta["modules"]
        assert "mod-b" in meta["modules"]
