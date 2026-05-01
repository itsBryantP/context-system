# `ctx pack` Temp File Filtering — Specification

**Related:** `specs/features/PACK_SPEC.md` (zero-config packaging)
**Feature class:** usability improvement — filter transient OS and application temp files before extraction

## Problem

`ctx pack` currently attempts to process every non-hidden file in the input directory tree, including temporary files created by the OS and applications. This causes:

1. **Unnecessary extraction warnings** — Word lock files (`~$document.docx`), macOS `.DS_Store`, Windows `Thumbs.db`, editor swap files (`.swp`, `~`) all get classified as `unsupported` or trigger extraction failures.

2. **Noise in scan/extract counts** — Users see inflated "skipped" or "failed" counts that don't represent actual content issues.

3. **Degraded UX for zero-config packing** — Running `ctx pack ~/Documents/` on a typical user directory produces dozens of spurious warnings that obscure real problems.

Example observed behavior:
```
Scanned 215 files: 187 supported, 28 skipped
  Warning: skipped .DS_Store: Unknown classification
  Warning: skipped ~$Quarterly Report.docx: Unknown classification
  Warning: skipped Thumbs.db: Unknown classification
  Warning: skipped .document.swp: Unknown classification
```

These files are never intended to be packed — they're transient artifacts that should be filtered at scan time, not at extraction time.

## Behavior

### Invariant

For any file `f` in the scan directory where `f` matches a **temp file pattern**, `scan_directory()` must **not** include `f` in the returned `ScanResult` list.

Temp file patterns are:
- **Word/Excel lock files**: `~$*` (prefix match)
- **macOS metadata**: `.DS_Store` (exact match)
- **Windows thumbnails**: `Thumbs.db` (case-insensitive exact match)
- **Generic temp files**: `*.tmp` (suffix match)
- **Editor swap files**: `*.swp`, `*.swo`, `*~` (suffix match)

These patterns are **always applied** — they are not user-configurable in this iteration.

### Algorithm

Update `scan_directory()` in `src/ctx/pack.py` to apply temp file filtering **after** the hidden-file check and **before** classification:

```python
def scan_directory(input_dir: Path) -> list[ScanResult]:
    """Recursively scan input_dir and classify every file by extension.
    
    Rules:
    - Hidden files and directories (name starts with '.' or '_') are skipped.
    - Temp files (OS/app artifacts like ~$*, .DS_Store, *.tmp) are skipped.
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
        # Skip temp files
        if _is_temp_file(path):
            continue
        classification = _EXT_MAP.get(path.suffix.lower(), "unsupported")
        results.append(ScanResult(source_path=path, classification=classification))
    
    return results
```

### Helper function

```python
def _is_temp_file(path: Path) -> bool:
    """Return True if path is a temporary OS/application artifact that should be filtered."""
    name = path.name
    # Word/Excel lock files
    if name.startswith("~$"):
        return True
    # macOS metadata
    if name == ".DS_Store":
        return True
    # Windows thumbnails (case-insensitive)
    if name.lower() == "thumbs.db":
        return True
    # Generic temp and swap files
    if name.endswith((".tmp", ".swp", ".swo", "~")):
        return True
    return False
```

### Logging

Temp files are **silently filtered** — no warning message. This matches the behavior for hidden files: if it's intentionally excluded by design, there's no need to alert the user.

If verbose logging is ever added to `ctx pack` (out of scope for this spec), temp-file filtering could log at DEBUG level: `"Filtered temp file: {path}"`.

## API

No public API changes. No CLI flags. No schema changes.

The filtering is **opaque to users** — temp files simply never appear in scan results.

## Tests

Add to `tests/test_pack.py`:

### `test_scan_directory_filters_word_lock_files`

```python
def test_scan_directory_filters_word_lock_files(tmp_path):
    """scan_directory excludes Word/Excel lock files (~$*)."""
    from ctx.pack import scan_directory
    
    (tmp_path / "report.docx").write_text("real")
    (tmp_path / "~$report.docx").write_text("lock")
    (tmp_path / "~$WRL0001.tmp").write_text("lock")
    
    results = scan_directory(tmp_path)
    paths = {r.source_path.name for r in results}
    
    assert "report.docx" in paths
    assert "~$report.docx" not in paths
    assert "~$WRL0001.tmp" not in paths
```

### `test_scan_directory_filters_os_artifacts`

```python
def test_scan_directory_filters_os_artifacts(tmp_path):
    """scan_directory excludes .DS_Store, Thumbs.db, and generic temp files."""
    from ctx.pack import scan_directory
    
    (tmp_path / "real.txt").write_text("content")
    (tmp_path / ".DS_Store").write_bytes(b"\x00\x00")
    (tmp_path / "Thumbs.db").write_bytes(b"\x00\x00")
    (tmp_path / "THUMBS.DB").write_bytes(b"\x00\x00")  # case variant
    (tmp_path / "cache.tmp").write_text("temp")
    
    results = scan_directory(tmp_path)
    paths = {r.source_path.name for r in results}
    
    assert "real.txt" in paths
    assert ".DS_Store" not in paths
    assert "Thumbs.db" not in paths
    assert "THUMBS.DB" not in paths
    assert "cache.tmp" not in paths
```

### `test_scan_directory_filters_editor_swap_files`

```python
def test_scan_directory_filters_editor_swap_files(tmp_path):
    """scan_directory excludes Vim swap files and backup files."""
    from ctx.pack import scan_directory
    
    (tmp_path / "notes.md").write_text("content")
    (tmp_path / ".notes.md.swp").write_text("swap")
    (tmp_path / ".notes.md.swo").write_text("swap")
    (tmp_path / "notes.md~").write_text("backup")
    
    results = scan_directory(tmp_path)
    paths = {r.source_path.name for r in results}
    
    assert "notes.md" in paths
    assert ".notes.md.swp" not in paths
    assert ".notes.md.swo" not in paths
    assert "notes.md~" not in paths
```

### `test_is_temp_file`

```python
def test_is_temp_file():
    """_is_temp_file correctly identifies temp file patterns."""
    from pathlib import Path
    from ctx.pack import _is_temp_file
    
    assert _is_temp_file(Path("~$report.docx")) is True
    assert _is_temp_file(Path(".DS_Store")) is True
    assert _is_temp_file(Path("Thumbs.db")) is True
    assert _is_temp_file(Path("THUMBS.DB")) is True
    assert _is_temp_file(Path("cache.tmp")) is True
    assert _is_temp_file(Path(".file.swp")) is True
    assert _is_temp_file(Path("backup~")) is True
    
    assert _is_temp_file(Path("report.docx")) is False
    assert _is_temp_file(Path("normal.txt")) is False
    assert _is_temp_file(Path("~notes.md")) is False  # ~ suffix only, not prefix
```

## Documentation

### AGENTS.md / CLAUDE.md

Update the "Key Conventions" > "Supported File Types" section to note:

> **Temp file filtering**: `ctx pack` automatically excludes OS and application temp files (Word lock files `~$*`, `.DS_Store`, `Thumbs.db`, `*.tmp`, `*.swp`, editor backups) at scan time. These files never appear in scan results or extraction logs.

### PACK_SPEC.md

Add a new subsection under "Scanning" (around line 30):

```markdown
#### Temp file filtering

The scanner silently excludes temporary files created by operating systems and applications:

| Pattern | Examples | Source |
|---------|----------|--------|
| `~$*` | `~$report.docx`, `~$WRL0001.tmp` | Word/Excel lock files |
| `.DS_Store` | `.DS_Store` | macOS metadata |
| `Thumbs.db` | `Thumbs.db`, `THUMBS.DB` | Windows thumbnails |
| `*.tmp` | `cache.tmp`, `download.tmp` | Generic temp files |
| `*.swp`, `*.swo` | `.notes.md.swp` | Vim swap files |
| `*~` | `backup~`, `document~` | Editor backup files |

These patterns are always applied and are not user-configurable.
```

## Out of Scope

- **User-configurable ignore patterns** — Future extension. Would require schema changes (new `ignore` field in module config or pack CLI flag) and merge logic with the default patterns. Tracked separately if users request custom exclusions.

- **Logging filtered files** — No DEBUG-level logging in this iteration. The `ctx pack` CLI is currently silent about temp files (matching its treatment of hidden files).

- **Ignoring lock files for *currently open* Office docs** — This spec filters all `~$*` files unconditionally. A more sophisticated approach (checking if the real file is also present) is unnecessary — lock files should never be packed regardless.

- **`.gitignore` integration** — Applying `.gitignore` patterns is a separate feature with different semantics (version-control intent vs. temp-file filtering).

## Acceptance

1. `pytest tests/test_pack.py -k temp` passes (all 4 new tests).

2. Running `ctx pack` on a directory containing:
   ```
   documents/
     report.docx
     ~$report.docx
     .DS_Store
     Thumbs.db
     notes.md
     .notes.md.swp
   ```
   
   Produces:
   ```
   Scanned 2 files: 2 supported, 0 skipped
   Extracted 2 files (0 failed)
   ```
   
   Only `report.docx` and `notes.md` are processed. No warnings about temp files.

3. `pytest --cov=src/ctx/pack --cov-fail-under=90` still passes (the new `_is_temp_file` helper is fully covered by `test_is_temp_file`).

4. Existing tests pass without modification — the change is strictly additive (fewer files scanned, but all valid files still scanned).
