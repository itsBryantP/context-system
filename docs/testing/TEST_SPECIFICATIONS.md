# ctx Test Specifications

**Version:** 2.0
**Date:** April 16, 2026

Test cases for the gaps identified in [TESTING_PLAN.md](./TESTING_PLAN.md). These use actual APIs from the codebase.

---

## CLI Tests (`tests/test_cli.py`)

All CLI tests use Click's `CliRunner`:

```python
from click.testing import CliRunner
from ctx.cli import cli

runner = CliRunner()
```

### init

| Test | Steps | Expected |
|------|-------|----------|
| Creates config in empty dir | `runner.invoke(cli, ['init'])` in isolated fs | Exit 0, `.context/config.yaml` exists |
| Fails if config exists | Run `init` twice | Exit non-zero, "already exists" in output |

### create

| Test | Steps | Expected |
|------|-------|----------|
| Scaffolds module | `runner.invoke(cli, ['create', 'my-mod'])` | Exit 0, `my-mod/module.yaml` + `my-mod/content/` exist |
| Module.yaml is valid | Load created `module.yaml` with `model_validate()` | No validation error |

### chunks

| Test | Steps | Expected |
|------|-------|----------|
| Outputs valid JSONL | Point at `tests/fixtures/sample-module` | Exit 0, each stdout line is valid JSON with `id`, `content`, `metadata` |
| Text format works | Add `-f text` flag | Exit 0, human-readable output |

### validate

| Test | Steps | Expected |
|------|-------|----------|
| Valid module passes | Point at sample module | Exit 0 |
| Invalid module fails | Point at empty dir | Exit non-zero |

### build

| Test | Steps | Expected |
|------|-------|----------|
| Builds JSONL | `init` + `create` + `build` | `.context/chunks/*.jsonl` exists |
| Force rebuilds | Build twice, second with `--force` | Both succeed, second rebuilds |
| Skips unchanged | Build twice without `--force` | Second reports skipped |

### pack

| Test | Steps | Expected |
|------|-------|----------|
| Streams JSONL | `pack` a dir of .md files | Exit 0, valid JSONL on stdout |
| Writes module dir | `pack` with `-o ./out` | `out/module.yaml` + `out/content/` exist |

### add / remove

| Test | Steps | Expected |
|------|-------|----------|
| Add installs module | `init` + `add ./module` | Module listed in config |
| Remove uninstalls | `add` then `remove` | Module gone from config |

---

## Schema Tests (`tests/test_schema.py`)

Test Pydantic models directly:

```python
from pydantic import ValidationError
from ctx.schema import ModuleConfig, ProjectConfig, ChunkingConfig, ChunkingStrategy
```

| Test | Input | Expected |
|------|-------|----------|
| Valid minimal config | `{name, version, description}` | Passes, defaults applied |
| Default chunking | Omit `chunking` field | `strategy=HEADING`, `heading_level=2`, `max_tokens=500`, `overlap_tokens=50` |
| Missing name | `{version, description}` only | `ValidationError` |
| Missing description | `{name, version}` only | `ValidationError` |
| Invalid strategy | `chunking.strategy="bogus"` | `ValidationError` |
| Valid strategies | `heading`, `fixed`, `definition` | All pass |
| ProjectConfig path ref | `modules: [{path: "./foo"}]` | Passes |
| ProjectConfig git ref | `modules: [{git: "https://..."}]` | Passes |
| Depends_on list | `depends_on: ["base", "utils"]` | Passes, list preserved |
| Tags list | `tags: ["a", "b"]` | Passes |

---

## Error Handling (additions to existing files)

### In `test_module.py`

| Test | Input | Expected |
|------|-------|----------|
| Nonexistent dir | `load_module(Path("/nope"))` | `FileNotFoundError` |
| Dir without module.yaml | `load_module(tmp_path)` | `FileNotFoundError` |

The first test already exists. Add the malformed YAML case:

| Test | Input | Expected |
|------|-------|----------|
| Malformed YAML | Write bad YAML to `module.yaml` | Exception raised (YAML parse or Pydantic) |

### In `test_extractors.py`

| Test | Input | Expected |
|------|-------|----------|
| Unsupported format | `get_extractor(source_with_unknown_type)` | `ValueError` |

---

## What's Already Well-Covered

These components have solid existing tests and don't need additional specs:

- **Pack pipeline** (`test_pack.py`, 1152 lines) — scanner, extraction, strategy selection, inference, chunking, output
- **Boxnote extraction** (`test_boxnote.py`, 413 lines) — ProseMirror JSON parsing
- **Extractors** (`test_extractors.py`, 291 lines) — PDF, PPTX, URL, Markdown
- **Claude Code integration** (`test_claude_code.py`, 205 lines) — symlinks, patching
- **Chunkers** (`test_chunker.py` + `test_definition_chunker.py`, 278 lines) — heading, fixed, definition
- **Git** (`test_git.py`, 120 lines) — URL parsing, clone, cache
- **Freshness** (`test_freshness.py`, 113 lines) — hashing, metadata, staleness
- **Deps** (`test_deps.py`, 53 lines) — parse_dep, check_dependencies
