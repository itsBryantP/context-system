"""Tests for Pydantic schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctx.schema import (
    ChunkingConfig,
    ChunkingStrategy,
    ModuleConfig,
    ModuleRef,
    ProjectConfig,
    Source,
    SourceType,
)


class TestModuleConfig:
    def test_only_name_required(self):
        config = ModuleConfig(name="test")
        assert config.name == "test"
        assert config.version == "0.1.0"
        assert config.description == ""
        assert config.tags == []
        assert config.depends_on == []
        assert config.sources == []

    def test_defaults_applied_to_chunking(self):
        config = ModuleConfig(name="test")
        assert config.chunking.strategy == ChunkingStrategy.HEADING
        assert config.chunking.max_tokens == 500
        assert config.chunking.overlap_tokens == 50
        assert config.chunking.heading_level == 2

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ModuleConfig(version="1.0.0", description="Test")

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValidationError):
            ModuleConfig(name="test", chunking={"strategy": "bogus"})

    def test_all_strategies_valid(self):
        for strategy in ChunkingStrategy:
            config = ModuleConfig(
                name="test", chunking={"strategy": strategy.value}
            )
            assert config.chunking.strategy == strategy

    def test_tags_and_depends(self):
        config = ModuleConfig(
            name="test",
            tags=["a", "b"],
            depends_on=["base", "utils"],
        )
        assert config.tags == ["a", "b"]
        assert config.depends_on == ["base", "utils"]

    def test_sources(self):
        config = ModuleConfig(
            name="test",
            sources=[
                {"type": "markdown", "path": "./doc.md"},
                {"type": "url", "url": "https://example.com/doc"},
            ],
        )
        assert len(config.sources) == 2
        assert config.sources[0].type == SourceType.MARKDOWN
        assert config.sources[1].type == SourceType.URL

    def test_custom_chunking_values(self):
        config = ModuleConfig(
            name="test",
            chunking={
                "strategy": "fixed",
                "max_tokens": 1000,
                "overlap_tokens": 100,
            },
        )
        assert config.chunking.strategy == ChunkingStrategy.FIXED
        assert config.chunking.max_tokens == 1000
        assert config.chunking.overlap_tokens == 100


class TestProjectConfig:
    def test_empty(self):
        config = ProjectConfig()
        assert config.modules == []
        assert config.output.chunks_dir == ".context/chunks"

    def test_path_module_ref(self):
        config = ProjectConfig(modules=[{"path": "./my-module"}])
        assert len(config.modules) == 1
        assert config.modules[0].path == "./my-module"
        assert config.modules[0].git is None

    def test_git_module_ref(self):
        config = ProjectConfig(
            modules=[{"git": "https://github.com/org/repo.git#sub@v1"}]
        )
        assert len(config.modules) == 1
        assert config.modules[0].git == "https://github.com/org/repo.git#sub@v1"
        assert config.modules[0].path is None


class TestModuleRef:
    def test_requires_one_source(self):
        with pytest.raises(ValidationError):
            ModuleRef()

    def test_rejects_both_path_and_git(self):
        with pytest.raises(ValidationError):
            ModuleRef(path="./foo", git="https://example.com/repo.git")


class TestChunkingConfig:
    def test_defaults(self):
        config = ChunkingConfig()
        assert config.strategy == ChunkingStrategy.HEADING
        assert config.max_tokens == 500
        assert config.overlap_tokens == 50
        assert config.heading_level == 2
        assert config.overrides == []
