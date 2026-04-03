"""Build metadata and freshness tracking for incremental builds."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

_META_FILE = ".build-meta.json"


def compute_module_hash(module_path: Path) -> str:
    """SHA-256 over all content/*.md files, sorted by relative path.

    Hashes both the relative path and the file bytes so renames are detected.
    Returns empty string if the content/ directory doesn't exist.
    """
    content_dir = module_path / "content"
    if not content_dir.exists():
        return ""
    h = hashlib.sha256()
    for md_file in sorted(content_dir.rglob("*.md")):
        h.update(str(md_file.relative_to(module_path)).encode())
        h.update(md_file.read_bytes())
    return h.hexdigest()


def load_build_meta(project_root: Path) -> dict:
    """Load .context/.build-meta.json; returns {} if missing or corrupt."""
    path = project_root / ".context" / _META_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_build_meta(project_root: Path, meta: dict) -> None:
    """Persist build metadata to .context/.build-meta.json."""
    path = project_root / ".context" / _META_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2))


def is_fresh(module_name: str, current_hash: str, meta: dict) -> bool:
    """Return True if the module's stored hash matches current_hash."""
    stored = meta.get("modules", {}).get(module_name, {})
    return bool(current_hash) and stored.get("source_hash") == current_hash


def record_build(
    project_root: Path,
    module_name: str,
    source_hash: str,
    chunk_count: int,
) -> None:
    """Record a successful build in .context/.build-meta.json."""
    meta = load_build_meta(project_root)
    meta.setdefault("modules", {})[module_name] = {
        "source_hash": source_hash,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chunk_count": chunk_count,
    }
    save_build_meta(project_root, meta)
