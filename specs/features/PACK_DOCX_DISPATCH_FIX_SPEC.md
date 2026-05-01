# `ctx pack` DOCX Dispatch Fix — Specification

**Related:** `specs/features/DOCX_SUPPORT_SPEC.md` (original DOCX feature)
**Bug class:** integration regression — feature implemented in isolation, never wired into `ctx pack`.

## Problem

`ctx pack` skips every `.docx` / `.docm` file with a `Warning: skipped <name>: Unknown classification: docx` message and counts each one as a failure. Observed on a real run:

```
Scanned 202 files: 187 supported, 15 skipped
  Warning: skipped Transcript.docx: Unknown classification: docx
  Warning: skipped CP4Z Dev Env Setup.docx: Unknown classification: docx
  ... (21 more)
Extracted 164 files (23 failed)
```

DOCX support is otherwise complete:
- `_EXT_MAP` in `src/ctx/pack.py:18-19` maps `.docx` / `.docm` → `"docx"`.
- `_CLS_TO_SOURCE_TYPE` in `src/ctx/pack.py:545` maps `"docx"` → `SourceType.DOCX`.
- `DocxExtractor` and `_extract_docx(...)` in `src/ctx/extractors/docx.py:19,52` produce frontmatter + markdown via Docling, with image filtering.
- `ExtractionConfig` in `src/ctx/schema.py:35-41` exposes `docx_remove_images` and `docx_filter_profile_icons`.

The only missing piece is the dispatch branch in `_extract_one` (`src/ctx/pack.py:163-183`). The function handles `markdown`, `plaintext`, `pdf`, `pptx`, `boxnote`, `html`, `structured`, then falls through to `raise ValueError(f"Unknown classification: {cls}")`. `extract_files` (`src/ctx/pack.py:142-150`) catches that exception and records it as a failure — so each `.docx` becomes one of the "23 failed" entries.

This breaks:
- **The advertised feature.** `CLAUDE.md` and `AGENTS.md` both list `.docx`/`.docm` as a supported `ctx pack` extension.
- **User trust in zero-config packing.** A user pointing `ctx pack` at a directory of mixed Office docs gets a silent partial result — the headline counts look fine, but ~12% of supported files are silently dropped.
- **Module quality.** `Transcript.docx`, technical specs, and threat models are missing from the packed module's chunks despite being scanned and counted as "supported."

## Behavior

### Invariant

For any `ScanResult r` produced by `scan_directory()` where `r.classification == "docx"` and `r.source_path` exists and is a readable `.docx`/`.docm` file:

```
extract_files([r], input_dir, tmp_dir) returns ([ExtractedFile(...)], [])
```

That is — no docx classified by the scanner is silently dropped to the failures list for *dispatch* reasons. Genuine extraction failures (corrupt file, Docling import missing, etc.) still surface as failures with the underlying error message — never as `Unknown classification: docx`.

### Algorithm

Add a single branch to `_extract_one` immediately before the terminal `raise`:

```python
if cls == "docx":
    return _extract_docx_file(src, out)
```

`_extract_docx_file` is a thin pack-side adapter (new helper, alongside `_extract_pdf`, `_extract_pptx_file`, etc.) that:

1. Imports `_extract_docx` from `ctx.extractors.docx` lazily.
2. Lazily constructs a single module-level `DocumentConverter` instance (caching via a module-level `_DOCX_CONVERTER` slot guarded by a `None` check) — Docling's converter does heavy model loading on first construction; reusing one across all docx files in a single `ctx pack` run cuts overhead from O(N) to O(1).
3. Calls `_extract_docx(src, converter, remove_images=True, filter_profile_icons=True)` to obtain the markdown string (with frontmatter).
4. Writes the result to `out` and returns `out`.

If `docling` is not importable, the existing `_IMPORT_MSG` from `extractors/docx.py` propagates through `_extract_docx`'s constructor path. The failure surfaces as a per-file failure with a clear "docling is required..." message, not as a dispatch error.

### Defaults

The pack-side adapter hardcodes `remove_images=True` and `filter_profile_icons=True` — the same defaults as `DocxExtractor.__init__` and `ExtractionConfig`. Plumbing `ExtractionConfig` through `_extract_one` is **out of scope** for this fix; `pack.py` does not currently thread any per-classification config through the dispatcher, and adding that pathway is a separate change. Users who need different defaults can use `ctx extract` with a configured module.

### Converter caching

The cached converter lives in a module-level variable in `pack.py` (e.g. `_DOCX_CONVERTER: Any = None`). It is **not** reset between `ctx pack` invocations within the same Python process — this is fine for the CLI (one-shot process) and acceptable for tests (each test process is fresh). No explicit teardown.

## API

### New private helper

```python
# src/ctx/pack.py

_DOCX_CONVERTER: Any = None  # Lazy DocumentConverter, shared across all docx files in a pack run.


def _extract_docx_file(src: Path, out: Path) -> Path:
    """Convert a .docx/.docm file to markdown via Docling and write to `out`."""
    global _DOCX_CONVERTER
    from ctx.extractors.docx import _extract_docx  # noqa: PLC0415

    if _DOCX_CONVERTER is None:
        from docling.document_converter import DocumentConverter  # noqa: PLC0415
        _DOCX_CONVERTER = DocumentConverter()

    markdown = _extract_docx(
        src,
        _DOCX_CONVERTER,
        remove_images=True,
        filter_profile_icons=True,
    )
    out.write_text(markdown, encoding="utf-8")
    return out
```

### `_extract_one` change

Insert the `docx` branch alphabetically among the existing branches (kept consistent with current ordering, which is roughly source-format complexity):

```python
def _extract_one(result: ScanResult, input_dir: Path, tmp_dir: Path) -> Path:
    cls = result.classification
    src = result.source_path
    out = _unique_md_path(src, input_dir, tmp_dir)

    if cls == "markdown":
        return _extract_markdown(src, out)
    if cls == "plaintext":
        return _extract_plaintext(src, out)
    if cls == "pdf":
        return _extract_pdf(src, out)
    if cls == "pptx":
        return _extract_pptx_file(src, out)
    if cls == "docx":                          # NEW
        return _extract_docx_file(src, out)    # NEW
    if cls == "boxnote":
        return _extract_boxnote(src, out)
    if cls == "html":
        return _extract_html(src, out)
    if cls == "structured":
        return _extract_structured(src, out)
    raise ValueError(f"Unknown classification: {cls}")
```

No public API changes. No schema changes. No CLI flag changes.

## Tests

Add to `tests/test_pack.py` (the file already covers the pack pipeline end-to-end, so this is where the regression belongs):

### `test_extract_one_dispatches_docx`

Direct dispatcher test using a monkey-patched `_extract_docx` to avoid loading Docling in the test:

```python
def test_extract_one_dispatches_docx(tmp_path, monkeypatch):
    """_extract_one routes .docx files to the docx handler instead of raising."""
    from ctx import pack

    src = tmp_path / "input" / "doc.docx"
    src.parent.mkdir()
    src.write_bytes(b"PK\x03\x04")  # Minimal zip header — never actually opened.

    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    captured: dict[str, Any] = {}

    def fake_extract(docx_path, converter, remove_images, filter_profile_icons):
        captured["path"] = docx_path
        captured["remove_images"] = remove_images
        captured["filter_profile_icons"] = filter_profile_icons
        return "---\nsource_type: docx\n---\n\n# stub\n"

    class FakeConverter: ...
    monkeypatch.setattr(pack, "_DOCX_CONVERTER", FakeConverter())
    monkeypatch.setattr("ctx.extractors.docx._extract_docx", fake_extract)

    result = pack.ScanResult(source_path=src, classification="docx")
    out_path = pack._extract_one(result, src.parent, tmp_dir)

    assert out_path.exists()
    assert out_path.read_text().startswith("---\nsource_type: docx\n---")
    assert captured["path"] == src
    assert captured["remove_images"] is True
    assert captured["filter_profile_icons"] is True
```

### `test_extract_files_does_not_skip_docx`

Pipeline-level test asserting `extract_files` returns the docx in the `extracted` list (not `failures`):

```python
def test_extract_files_does_not_skip_docx(tmp_path, monkeypatch):
    """extract_files() must route .docx through the docx handler, not record a failure."""
    from ctx import pack

    monkeypatch.setattr(pack, "_DOCX_CONVERTER", object())
    monkeypatch.setattr(
        "ctx.extractors.docx._extract_docx",
        lambda *a, **k: "---\nsource_type: docx\n---\n\n# ok\n",
    )

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    docx_path = input_dir / "report.docx"
    docx_path.write_bytes(b"PK\x03\x04")

    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    scan = [pack.ScanResult(source_path=docx_path, classification="docx")]
    extracted, failures = pack.extract_files(scan, input_dir, tmp_dir)

    assert failures == []
    assert len(extracted) == 1
    assert extracted[0].classification == "docx"
```

### `test_pack_docx_with_real_docling` (optional, marked slow)

Only if a small `.docx` fixture is added under `tests/fixtures/` — exercises the full path including Docling. Gated behind `pytest.importorskip("docling")` so CI without the extras still passes.

### Regression coverage for the original failure mode

The combination above guarantees: if a future refactor drops the `docx` branch from `_extract_one`, `test_extract_files_does_not_skip_docx` fails with the `failures != []` assertion, and the user-visible "Unknown classification: docx" symptom is caught.

## Documentation

No CLAUDE.md / AGENTS.md changes — both already advertise `.docx` support in `ctx pack`. This fix makes reality match the docs.

## Out of Scope

- Plumbing `ExtractionConfig` through `_extract_one` so users can override `docx_remove_images` / `docx_filter_profile_icons` for `ctx pack`. The current `ctx pack` pipeline does not consume per-classification config; adding that pathway is a larger change and is tracked separately.
- Any change to `DocxExtractor` itself, `_extract_docx`, or the image-filtering heuristics.
- Legacy `.doc` support — explicitly classified as `unsupported` and remains so.
- Progress reporting / parallelism for large docx batches — orthogonal to this dispatch fix.

## Acceptance

1. `pytest tests/test_pack.py -k docx` passes.
2. Re-running the failing command (`ctx pack /Users/bpanyar/Documents/IBM --install --tool bob`) on the same input directory yields:
   - Zero `Unknown classification: docx` warnings.
   - The previously-dropped 23 `.docx` files appear in the `Extracted` count.
   - The packed module under `~/github/.../internal-context/.context/packed/ibm/` contains chunks sourced from the previously-skipped docx files (verifiable by grepping a known docx filename in the JSONL).
3. `pytest --cov=src/ctx/pack --cov-fail-under=90` still passes (the new helper is small and fully covered by the two tests above).
