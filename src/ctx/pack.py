"""ctx pack — zero-config module packaging from any directory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ── File classification ───────────────────────────────────────────────────────

_EXT_MAP: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "plaintext",
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".html": "html",
    ".htm": "html",
    ".yaml": "structured",
    ".yml": "structured",
    ".json": "structured",
}


@dataclass
class ScanResult:
    """A single file discovered during directory scanning."""
    source_path: Path
    classification: str  # markdown | plaintext | pdf | pptx | html | structured | unsupported


def scan_directory(input_dir: Path) -> list[ScanResult]:
    """Recursively scan input_dir and classify every file by extension.

    Rules:
    - Hidden files and directories (name starts with '.' or '_') are skipped.
    - Files are sorted by path for deterministic output.
    - Returns all files, including unsupported ones (callers decide what to skip).
    """
    input_dir = input_dir.resolve()
    results: list[ScanResult] = []

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        # Skip anything inside a hidden or underscore-prefixed directory
        if any(part.startswith((".", "_")) for part in path.relative_to(input_dir).parts):
            continue
        classification = _EXT_MAP.get(path.suffix.lower(), "unsupported")
        results.append(ScanResult(source_path=path, classification=classification))

    return results


# ── Name normalization ────────────────────────────────────────────────────────

def kebab_case(name: str) -> str:
    """Normalize a directory name to a valid kebab-case module name.

    Examples:
        "API Knowledge Base"  →  "api-knowledge-base"
        "My_Docs"             →  "my-docs"
        "v2_api_specs"        →  "v2-api-specs"
        "  hello--world  "    →  "hello-world"
    """
    name = name.strip()
    # Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)
    # Strip characters that aren't alphanumeric or hyphens
    name = re.sub(r"[^\w-]", "", name)
    # Collapse multiple hyphens
    name = re.sub(r"-{2,}", "-", name)
    # Lowercase and strip leading/trailing hyphens
    return name.lower().strip("-")
