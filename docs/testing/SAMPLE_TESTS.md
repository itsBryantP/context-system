# Sample Test Implementations

**Version:** 2.0
**Date:** April 16, 2026

Working examples for the test gaps identified in [TEST_SPECIFICATIONS.md](./TEST_SPECIFICATIONS.md). These use actual APIs from the codebase.

---

## CLI Tests

**File:** `tests/test_cli.py`

```python
"""Tests for CLI commands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ctx.cli import cli

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample-module"


@pytest.fixture
def runner():
    return CliRunner()


class TestInit:
    def test_creates_config(self, runner, tmp_path):
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".context" / "config.yaml").exists()

    def test_fails_if_config_exists(self, runner, tmp_path):
        # First init
        runner.invoke(cli, ["init", str(tmp_path)])
        # Second init should fail
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code != 0


class TestCreate:
    def test_scaffolds_module(self, runner, tmp_path):
        result = runner.invoke(cli, ["create", "my-mod", "--path", str(tmp_path)])
        assert result.exit_code == 0

        module_dir = tmp_path / "my-mod"
        assert (module_dir / "module.yaml").exists()
        assert (module_dir / "content").is_dir()


class TestChunks:
    def test_outputs_valid_jsonl(self, runner):
        result = runner.invoke(cli, ["chunks", str(SAMPLE)])
        assert result.exit_code == 0

        for line in result.output.strip().splitlines():
            chunk = json.loads(line)
            assert "id" in chunk
            assert "content" in chunk
            assert "metadata" in chunk

    def test_text_format(self, runner):
        result = runner.invoke(cli, ["chunks", str(SAMPLE), "-f", "text"])
        assert result.exit_code == 0
        assert len(result.output) > 0


class TestValidate:
    def test_valid_module(self, runner):
        result = runner.invoke(cli, ["validate", str(SAMPLE)])
        assert result.exit_code == 0

    def test_invalid_module(self, runner, tmp_path):
        result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code != 0


class TestPack:
    def test_streams_jsonl(self, runner, tmp_path):
        # Create a dir with markdown
        (tmp_path / "doc.md").write_text("# Title\n\n## Section\n\nContent here.")

        result = runner.invoke(cli, ["pack", str(tmp_path)])
        assert result.exit_code == 0

        for line in result.output.strip().splitlines():
            chunk = json.loads(line)
            assert "id" in chunk

    def test_writes_module_dir(self, runner, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.md").write_text("# Doc\n\n## Part\n\nText.")

        out = tmp_path / "out"
        result = runner.invoke(cli, ["pack", str(src), "-o", str(out)])
        assert result.exit_code == 0
        assert (out / "module.yaml").exists()
        assert (out / "content").is_dir()
```

---

## Schema Tests

**File:** `tests/test_schema.py`

```python
"""Tests for Pydantic schema models."""

import pytest
from pydantic import ValidationError

from ctx.schema import ModuleConfig, ProjectConfig, ChunkingStrategy


class TestModuleConfig:
    def test_valid_minimal(self):
        config = ModuleConfig(
            name="test", version="1.0.0", description="A test module"
        )
        assert config.name == "test"
        assert config.version == "1.0.0"

    def test_defaults_applied(self):
        config = ModuleConfig(
            name="test", version="1.0.0", description="Test"
        )
        assert config.chunking.strategy == ChunkingStrategy.HEADING
        assert config.chunking.max_tokens == 500
        assert config.chunking.overlap_tokens == 50

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ModuleConfig(version="1.0.0", description="Test")

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            ModuleConfig(name="test", version="1.0.0")

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValidationError):
            ModuleConfig(
                name="test",
                version="1.0.0",
                description="Test",
                chunking={"strategy": "bogus"},
            )

    def test_all_strategies_valid(self):
        for strategy in ChunkingStrategy:
            config = ModuleConfig(
                name="test",
                version="1.0.0",
                description="Test",
                chunking={"strategy": strategy.value},
            )
            assert config.chunking.strategy == strategy

    def test_tags_and_depends(self):
        config = ModuleConfig(
            name="test",
            version="1.0.0",
            description="Test",
            tags=["a", "b"],
            depends_on=["base"],
        )
        assert config.tags == ["a", "b"]
        assert config.depends_on == ["base"]


class TestProjectConfig:
    def test_path_module_ref(self):
        config = ProjectConfig(modules=[{"path": "./my-module"}])
        assert len(config.modules) == 1

    def test_git_module_ref(self):
        config = ProjectConfig(
            modules=[{"git": "https://github.com/org/repo.git#sub@v1"}]
        )
        assert len(config.modules) == 1

    def test_empty_modules(self):
        config = ProjectConfig(modules=[])
        assert config.modules == []
```

---

## Error Handling Additions

Add to `tests/test_module.py`:

```python
def test_load_module_malformed_yaml(tmp_path):
    """Malformed YAML in module.yaml should raise."""
    module_dir = tmp_path / "bad"
    module_dir.mkdir()
    (module_dir / "module.yaml").write_text("name: test\nversion: [unclosed")

    with pytest.raises(Exception):
        load_module(module_dir)
```
