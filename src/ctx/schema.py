"""Pydantic models for module.yaml and config.yaml."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ChunkingStrategy(str, Enum):
    HEADING = "heading"
    FIXED = "fixed"
    DEFINITION = "definition"


class SourceType(str, Enum):
    MARKDOWN = "markdown"
    PDF = "pdf"
    PPTX = "pptx"
    URL = "url"


class RefreshSchedule(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# --- module.yaml models ---


class Source(BaseModel):
    type: SourceType
    path: Optional[str] = None
    url: Optional[str] = None
    refresh: Optional[RefreshSchedule] = None


class ChunkingOverride(BaseModel):
    pattern: str
    strategy: Optional[ChunkingStrategy] = None
    max_tokens: Optional[int] = None
    overlap_tokens: Optional[int] = None
    heading_level: Optional[int] = None


class ChunkingConfig(BaseModel):
    strategy: ChunkingStrategy = ChunkingStrategy.HEADING
    max_tokens: int = 500
    overlap_tokens: int = 50
    heading_level: int = 2
    overrides: list[ChunkingOverride] = Field(default_factory=list)


class ModuleConfig(BaseModel):
    """Schema for module.yaml."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)


# --- config.yaml models ---


class ModuleRef(BaseModel):
    path: str


class ChunkDefaults(BaseModel):
    max_tokens: int = 500
    overlap_tokens: int = 50
    strategy: ChunkingStrategy = ChunkingStrategy.HEADING


class OutputConfig(BaseModel):
    chunks_dir: str = ".context/chunks"
    claude_md: bool = True


class ProjectConfig(BaseModel):
    """Schema for .context/config.yaml."""

    modules: list[ModuleRef] = Field(default_factory=list)
    chunk_defaults: ChunkDefaults = Field(default_factory=ChunkDefaults)
    output: OutputConfig = Field(default_factory=OutputConfig)
