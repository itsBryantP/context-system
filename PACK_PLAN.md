# ctx pack — Implementation Plan

## Overview

Implement the `ctx pack` command as specified in `PACK_SPEC.md`. The command takes any directory of mixed files and produces JSONL chunks in one step, with no module.yaml or content/ convention required.

All logic lives in a single new module (`src/ctx/pack.py`) plus the CLI wiring. Everything else — extractors, chunkers, JSONL serialization — already exists and is reused directly.

---

## Phases

### Phase 1: Scanner and File Classification

**Goal:** Given a directory, produce a classified list of files ready for extraction.

| # | What | Details |
|---|------|---------|
| 1 | `scan_directory(input_dir) -> list[ScanResult]` | Recursively walk the directory. Classify each file by extension. Skip hidden files/dirs (`.` or `_` prefix). Return sorted `(path, classification)` pairs. |
| 2 | `ScanResult` dataclass | `source_path: Path`, `classification: str` — one of `markdown`, `plaintext`, `pdf`, `pptx`, `html`, `structured`, `unsupported` |
| 3 | Extension mapping | `.md`/`.markdown` → markdown, `.txt` → plaintext, `.pdf` → pdf, `.pptx`/`.ppt` → pptx, `.html`/`.htm` → html, `.yaml`/`.yml`/`.json` → structured, everything else → unsupported |
| 4 | `kebab_case(name) -> str` | Normalize a directory name: lowercase, replace spaces/underscores with hyphens, strip non-alphanumeric chars. Used for auto-deriving module name. |

**Tests:** scan on a tmp_path with mixed file types; hidden file skipping; kebab-case normalization edge cases.

**Existing code reused:** None — this is new scan logic.

---

### Phase 2: Extraction into Temp Space

**Goal:** Given scan results, extract every file to markdown in a temporary directory. Never touch the input.

| # | What | Details |
|---|------|---------|
| 5 | `extract_files(scan_results, tmp_dir) -> list[ExtractedFile]` | For each scanned file, produce a markdown file in `tmp_dir`. Returns `ExtractedFile(original_path, md_path, classification)`. |
| 6 | Markdown/plaintext handling | Copy to tmp_dir as-is (strip frontmatter for `.md` using existing `_strip_frontmatter`). `.txt` files get a `# filename` heading prepended. |
| 7 | PDF/PPTX extraction | Call existing `PDFExtractor.extract()` and `PPTXExtractor.extract()` with the tmp_dir as output. |
| 8 | HTML extraction | If `markdownify` is available, convert HTML → markdown. Otherwise warn and skip. No new extractor class needed — inline `markdownify.markdownify()` call since the URL extractor's `_to_markdown` already does this but is coupled to URL fetching. Factor out a small `html_to_markdown(html: str) -> str` helper or call markdownify directly. |
| 9 | Structured data (YAML/JSON) | Read file, wrap in a fenced code block with the filename as H1 heading. No external dependency. |
| 10 | Error handling per file | Wrap each extraction in try/except. On failure, log a warning to stderr via `click.echo(..., err=True)` and continue. Track failures in a list returned alongside successes. |

**Tests:** extract a mix of files (markdown, txt, PDF mock, structured data); verify frontmatter stripping; verify structured data fencing; verify failure isolation.

**Existing code reused:**
- `ctx.extractors.markdown._strip_frontmatter` — frontmatter stripping
- `ctx.extractors.pdf.PDFExtractor` — PDF extraction
- `ctx.extractors.pptx.PPTXExtractor` — PPTX extraction
- `markdownify.markdownify` — HTML conversion (optional dep)

---

### Phase 3: Strategy Auto-Selection

**Goal:** For each extracted markdown file, analyze its structure and pick the best chunking strategy.

| # | What | Details |
|---|------|---------|
| 11 | `select_strategy(content, max_tokens) -> ChunkingStrategy` | Implement the heuristic from the spec. Count H2 headings, H3/H4 headings, bold-term definition patterns, and total tokens. Return `DEFINITION`, `HEADING`, or `FIXED`. |
| 12 | Per-file strategy map | Build a `dict[Path, ChunkingStrategy]` mapping each extracted file to its chosen strategy. If `--strategy` is set, use it for every file. |

**Tests:** documents that should trigger each strategy path; the total-tokens-under-threshold shortcut; override flag forcing a single strategy.

**Existing code reused:**
- `ctx.chunker.base.count_tokens` — token counting
- `ctx.schema.ChunkingStrategy` — the enum

---

### Phase 4: Auto-Detection (Name, Description, Tags)

**Goal:** Derive module metadata from the content without user input.

| # | What | Details |
|---|------|---------|
| 13 | `infer_name(input_dir, override)` | If `--name` given, use it. Otherwise kebab-case the directory name. |
| 14 | `infer_description(md_contents, dir_name)` | Scan extracted files for the first H1 heading. If found, use its text. Otherwise `"Context module packed from <dir-name>"`. |
| 15 | `infer_tags(md_contents, override)` | If `--tags` given, split on commas. Otherwise collect H1–H3 heading texts and `**bold**` terms across all files, tokenize to lowercase words, drop stop words and short words, return top 3–5 terms that appear in 2+ documents. |
| 16 | Stop word list | A small hardcoded set (~50 common English words: the, and, is, for, with, ...). No external dependency. |

**Tests:** name normalization; description from first H1; tag extraction from multi-doc headings; fallback when no H1 exists; stop word filtering.

**Existing code reused:** None — new inference logic.

---

### Phase 5: Chunking and JSONL Assembly

**Goal:** Run each file through its selected chunker and assemble the final JSONL output.

| # | What | Details |
|---|------|---------|
| 17 | `chunk_files(extracted_files, strategies, module_name, tags, max_tokens, overlap)` | For each file, instantiate the appropriate chunker and run it. Set `source_file` to the **original** input path relative to the input directory (e.g., `spec.pdf`, not `content/spec.md`). Return all chunks. |
| 18 | Majority strategy detection | For `-o` output, determine which strategy was used most often and set it as the module-level default in `module.yaml`. File-level deviations become `overrides`. |
| 19 | JSONL serialization | Use existing `chunks_to_jsonl()` from `ctx.integrations.jsonl`. |

**Tests:** chunk a mixed set of files with different strategies; verify source_file refers to original paths; verify majority strategy detection.

**Existing code reused:**
- `ctx.chunker.heading.HeadingChunker`
- `ctx.chunker.fixed.FixedChunker`
- `ctx.chunker.definition.DefinitionChunker`
- `ctx.integrations.jsonl.chunks_to_jsonl`

---

### Phase 6: Output Modes and CLI Wiring

**Goal:** Implement the three output modes and add the `pack` command to the CLI.

| # | What | Details |
|---|------|---------|
| 20 | stdout output (default) | Print JSONL to stdout via `click.echo`. All progress/warnings on stderr. |
| 21 | `-f text` output | Print human-readable chunk summaries (reuse the format from the existing `chunks` command). |
| 22 | `-o <path>` module output | Create a standard module directory: write `content/` files, `module.yaml` (with auto-detected config + overrides + sources), and `chunks/<name>.jsonl`. Error if path exists. |
| 23 | `--install` mode | Materialize the module at `.context/packed/<name>/`. Then call existing `install_module()` from `ctx.integrations.claude_code` and add to `.context/config.yaml` via existing `save_config()`. |
| 24 | CLI `pack` command | Wire everything together in `cli.py`. Arguments: `directory` (required). Options: `--name`, `--description`, `--tags`, `--strategy`, `--max-tokens`, `--overlap`, `-o/--output`, `--install`, `-f/--format`. |
| 25 | Progress output | Structured stderr output: scan summary, per-file extraction status, per-file chunking summary, total. |

**Tests:** end-to-end test: create a tmp_path with mixed files, run the pack pipeline, verify JSONL output; `-o` test: verify module.yaml contents, content/ files, chunks/ file; `--install` test: verify `.context/packed/` and config.yaml updated.

**Existing code reused:**
- `ctx.integrations.jsonl.chunks_to_jsonl`, `write_jsonl`
- `ctx.integrations.claude_code.install_module`
- `ctx.config.load_config`, `save_config`
- `ctx.schema.ModuleConfig`, `ModuleRef`, `ChunkingConfig`, `ChunkingOverride`, `Source`, `SourceType`

---

## File Plan

### New files

| File | Phase | What |
|------|-------|------|
| `src/ctx/pack.py` | 1–5 | All pack logic: `scan_directory`, `extract_files`, `select_strategy`, `infer_*`, `chunk_files`, `write_module`, `pack` (orchestrator) |
| `tests/test_pack.py` | 1–6 | Tests for each phase: scanning, extraction, strategy selection, inference, chunking, output modes |

### Modified files

| File | Phase | What |
|------|-------|------|
| `src/ctx/cli.py` | 6 | Add the `pack` Click command with all options |

### Unchanged files

Everything else in the codebase remains unchanged. `pack.py` imports from existing modules but introduces no changes to their interfaces.

---

## Dependency Map

Each phase builds on the previous one. Within a phase, items are independent and can be implemented in any order.

```
Phase 1: Scanner           ← no dependencies
Phase 2: Extraction        ← depends on Phase 1 (scan results)
Phase 3: Strategy          ← depends on Phase 2 (extracted markdown)
Phase 4: Auto-detection    ← depends on Phase 2 (extracted markdown)
Phase 5: Chunking          ← depends on Phases 2, 3, 4 (files, strategies, metadata)
Phase 6: Output + CLI      ← depends on Phase 5 (chunks ready)
```

Phases 3 and 4 are independent of each other and can be implemented in parallel.

---

## Verification

After each phase, the following should be testable:

| Phase | Verification |
|-------|-------------|
| 1 | `scan_directory` returns correct classifications for a mixed directory |
| 2 | `extract_files` produces markdown in tmp_dir for each supported type |
| 3 | `select_strategy` returns the expected strategy for each content shape |
| 4 | `infer_name/description/tags` produce sensible defaults from sample content |
| 5 | `chunk_files` produces valid Chunk objects with correct source_file metadata |
| 6 | `ctx pack <dir>` runs end-to-end and produces valid JSONL; `-o` produces a valid module |

### End-to-end smoke test

```bash
# Create a test directory with mixed content
mkdir /tmp/test-pack
echo "# Overview\n\nSome content about APIs.\n\n## Authentication\n\nUse tokens.\n" > /tmp/test-pack/overview.md
echo "**API**: Application Programming Interface.\n**SDK**: Software Development Kit.\n" > /tmp/test-pack/glossary.md
echo "Plain text notes from a meeting." > /tmp/test-pack/notes.txt
echo '{"database": {"host": "localhost"}}' > /tmp/test-pack/config.json

# Pack it
ctx pack /tmp/test-pack/
# Should produce JSONL on stdout with chunks from all 4 files

# Write a module
ctx pack /tmp/test-pack/ -o /tmp/test-module
# Should produce module.yaml + content/ + chunks/
cat /tmp/test-module/module.yaml
# Should show auto-detected name, tags, strategy, overrides, sources
```
