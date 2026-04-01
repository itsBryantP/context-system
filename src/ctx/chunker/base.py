"""Abstract base class for chunking strategies and Chunk data model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import tiktoken


@dataclass
class Chunk:
    """A single chunk of content with metadata."""

    id: str
    module: str
    source_file: str
    section_path: list[str]
    content: str
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if "token_count" not in self.metadata:
            self.metadata["token_count"] = count_tokens(self.content)


_encoder: tiktoken.Encoding | None = None


def get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    return len(get_encoder().encode(text))


def slugify(text: str) -> str:
    """Convert heading text to a URL-safe slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug


class ChunkStrategy(ABC):
    """Abstract base for chunking strategies."""

    @abstractmethod
    def chunk(
        self,
        content: str,
        *,
        module_name: str,
        source_file: str,
        tags: list[str],
        version: str,
        max_tokens: int = 500,
        overlap_tokens: int = 50,
        **kwargs,
    ) -> list[Chunk]:
        """Split content into chunks."""
        ...
