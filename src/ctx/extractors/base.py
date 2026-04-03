"""Abstract base class for extractor plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ctx.schema import Source


class Extractor(ABC):
    """Convert a source (file or URL) into markdown content files."""

    @abstractmethod
    def can_handle(self, source: Source) -> bool:
        """Return True if this extractor handles the given source type."""
        ...

    @abstractmethod
    def extract(self, source: Source, output_dir: Path) -> list[Path]:
        """Extract source into markdown files under output_dir.

        Returns the list of files created.
        """
        ...
