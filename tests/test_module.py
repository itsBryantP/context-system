"""Tests for module loading and validation."""

from pathlib import Path

import pytest

from ctx.module import get_content_files, load_module, validate_module
from ctx.schema import ChunkingStrategy

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample-module"


def test_load_module():
    mod = load_module(SAMPLE)
    assert mod.name == "sample-module"
    assert mod.version == "1.0.0"
    assert mod.description == "A sample module for testing"
    assert "test" in mod.tags
    assert mod.chunking.strategy == ChunkingStrategy.HEADING


def test_load_module_missing_yaml(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_module(tmp_path)


def test_get_content_files():
    files = get_content_files(SAMPLE)
    assert len(files) >= 1
    assert all(f.suffix == ".md" for f in files)


def test_get_content_files_missing_dir(tmp_path):
    assert get_content_files(tmp_path) == []


def test_validate_module_valid():
    issues = validate_module(SAMPLE)
    assert issues == []


def test_validate_module_missing_yaml(tmp_path):
    issues = validate_module(tmp_path)
    assert any("module.yaml" in i for i in issues)


def test_validate_module_missing_content(tmp_path):
    import yaml
    (tmp_path / "module.yaml").write_text(yaml.dump({"name": "test", "version": "0.1.0"}))
    issues = validate_module(tmp_path)
    assert any("content" in i.lower() for i in issues)
