"""Tests for CLI commands."""

from __future__ import annotations

import json
import shutil
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

    def test_idempotent(self, runner, tmp_path):
        # init is idempotent — running twice should succeed both times.
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0


class TestCreate:
    def test_scaffolds_module(self, runner, tmp_path):
        result = runner.invoke(cli, ["create", "my-mod", "--path", str(tmp_path)])
        assert result.exit_code == 0

        module_dir = tmp_path / "my-mod"
        assert (module_dir / "module.yaml").exists()
        assert (module_dir / "content").is_dir()
        assert (module_dir / "content" / "overview.md").exists()

    def test_fails_if_dir_exists(self, runner, tmp_path):
        (tmp_path / "dupe").mkdir()
        result = runner.invoke(cli, ["create", "dupe", "--path", str(tmp_path)])
        assert result.exit_code != 0
        assert "already exists" in result.output.lower()


class TestChunks:
    def test_outputs_valid_jsonl(self, runner):
        result = runner.invoke(cli, ["chunks", str(SAMPLE)])
        assert result.exit_code == 0

        lines = [line for line in result.output.strip().splitlines() if line]
        assert len(lines) > 0

        for line in lines:
            chunk = json.loads(line)
            assert "id" in chunk
            assert "content" in chunk
            assert "metadata" in chunk
            assert "module" in chunk
            assert chunk["module"] == "sample-module"

    def test_text_format(self, runner):
        result = runner.invoke(cli, ["chunks", str(SAMPLE), "-f", "text"])
        assert result.exit_code == 0
        assert "tokens" in result.output


class TestValidate:
    def test_valid_module(self, runner):
        result = runner.invoke(cli, ["validate", str(SAMPLE)])
        assert result.exit_code == 0

    def test_invalid_module(self, runner, tmp_path):
        # Empty dir has no module.yaml
        result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code != 0


class TestBuild:
    def test_builds_jsonl(self, runner, tmp_path):
        # Set up a project with the sample module copied in
        runner.invoke(cli, ["init", str(tmp_path)])
        mod_copy = tmp_path / "sample-module"
        shutil.copytree(SAMPLE, mod_copy)
        add_result = runner.invoke(
            cli, ["add", str(mod_copy), "--project", str(tmp_path)]
        )
        assert add_result.exit_code == 0

        result = runner.invoke(cli, ["build", "--project", str(tmp_path)])
        assert result.exit_code == 0

        jsonl = tmp_path / ".context" / "chunks" / "sample-module.jsonl"
        assert jsonl.exists()
        assert jsonl.stat().st_size > 0

    def test_skips_unchanged(self, runner, tmp_path):
        runner.invoke(cli, ["init", str(tmp_path)])
        mod_copy = tmp_path / "sample-module"
        shutil.copytree(SAMPLE, mod_copy)
        runner.invoke(cli, ["add", str(mod_copy), "--project", str(tmp_path)])

        runner.invoke(cli, ["build", "--project", str(tmp_path)])
        result = runner.invoke(cli, ["build", "--project", str(tmp_path)])
        assert result.exit_code == 0
        assert "skipped" in result.output.lower() or "up to date" in result.output.lower()

    def test_force_rebuilds(self, runner, tmp_path):
        runner.invoke(cli, ["init", str(tmp_path)])
        mod_copy = tmp_path / "sample-module"
        shutil.copytree(SAMPLE, mod_copy)
        runner.invoke(cli, ["add", str(mod_copy), "--project", str(tmp_path)])

        runner.invoke(cli, ["build", "--project", str(tmp_path)])
        result = runner.invoke(
            cli, ["build", "--project", str(tmp_path), "--force"]
        )
        assert result.exit_code == 0
        assert "skipped" not in result.output.lower()

    def test_fails_without_modules(self, runner, tmp_path):
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(cli, ["build", "--project", str(tmp_path)])
        assert result.exit_code != 0


class TestPack:
    def test_streams_jsonl(self, runner, tmp_path):
        (tmp_path / "doc.md").write_text(
            "# Title\n\n## Section One\n\nContent here.\n\n## Section Two\n\nMore text.\n"
        )
        # Use stdout, not output — pack writes progress to stderr.
        result = runner.invoke(cli, ["pack", str(tmp_path)])
        assert result.exit_code == 0

        lines = [line for line in result.stdout.strip().splitlines() if line]
        assert len(lines) > 0
        for line in lines:
            chunk = json.loads(line)
            assert "id" in chunk
            assert "content" in chunk

    def test_writes_module_dir(self, runner, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.md").write_text("# Doc\n\n## Part\n\nText.\n")

        out = tmp_path / "out"
        result = runner.invoke(cli, ["pack", str(src), "-o", str(out)])
        assert result.exit_code == 0
        assert (out / "module.yaml").exists()
        assert (out / "content").is_dir()

    def test_fails_if_output_exists(self, runner, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.md").write_text("# Doc\n\nContent.\n")

        out = tmp_path / "out"
        out.mkdir()
        result = runner.invoke(cli, ["pack", str(src), "-o", str(out)])
        assert result.exit_code != 0


class TestAddRemove:
    def test_add_registers_module(self, runner, tmp_path):
        runner.invoke(cli, ["init", str(tmp_path)])
        mod_copy = tmp_path / "sample-module"
        shutil.copytree(SAMPLE, mod_copy)

        result = runner.invoke(
            cli, ["add", str(mod_copy), "--project", str(tmp_path)]
        )
        assert result.exit_code == 0

        config_yaml = (tmp_path / ".context" / "config.yaml").read_text()
        assert "sample-module" in config_yaml

    def test_remove_unregisters_module(self, runner, tmp_path):
        runner.invoke(cli, ["init", str(tmp_path)])
        mod_copy = tmp_path / "sample-module"
        shutil.copytree(SAMPLE, mod_copy)
        runner.invoke(cli, ["add", str(mod_copy), "--project", str(tmp_path)])

        result = runner.invoke(
            cli, ["remove", "sample-module", "--project", str(tmp_path)]
        )
        assert result.exit_code == 0

        config_yaml = (tmp_path / ".context" / "config.yaml").read_text()
        assert "sample-module" not in config_yaml


class TestList:
    def test_empty_project(self, runner, tmp_path):
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(cli, ["list", "--project", str(tmp_path)])
        assert result.exit_code == 0
        assert "no modules" in result.output.lower()

    def test_with_module(self, runner, tmp_path):
        runner.invoke(cli, ["init", str(tmp_path)])
        mod_copy = tmp_path / "sample-module"
        shutil.copytree(SAMPLE, mod_copy)
        runner.invoke(cli, ["add", str(mod_copy), "--project", str(tmp_path)])

        result = runner.invoke(cli, ["list", "--project", str(tmp_path)])
        assert result.exit_code == 0
        assert "sample-module" in result.output
