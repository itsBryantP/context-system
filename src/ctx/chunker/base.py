"""Abstract base class for chunking strategies and Chunk data model."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

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
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug


# ── Metadata helpers (Phase 3) ────────────────────────────────────────────────


_FENCE_RE = re.compile(r"^```(.*)$", re.MULTILINE)


def detect_code(content: str) -> tuple[bool, str | None]:
    """Return (has_code, language) based on triple-backtick fences.

    Requires an even count of fence markers (≥ 2). Language is the first
    whitespace-delimited token of the opening fence's info string, lowercased.
    """
    fences = _FENCE_RE.findall(content)
    if len(fences) < 2 or len(fences) % 2 != 0:
        return (False, None)
    info = fences[0].strip()
    if info:
        return (True, info.split()[0].lower())
    return (True, None)


def compute_file_id(source_file: str) -> str:
    """Stable 12-char hash of the source file path."""
    return hashlib.sha256(source_file.encode("utf-8")).hexdigest()[:12]


def derive_doc_title(source_file: str) -> str:
    """Fallback doc title from a source file path when no H1 is found."""
    stem = Path(source_file).stem
    return stem.replace("_", " ").replace("-", " ").title()


def apply_chain_metadata(chunks: list[Chunk]) -> None:
    """Populate prev_chunk_id / next_chunk_id across a file's chunk list."""
    n = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk.metadata["prev_chunk_id"] = chunks[i - 1].id if i > 0 else None
        chunk.metadata["next_chunk_id"] = chunks[i + 1].id if i < n - 1 else None


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
