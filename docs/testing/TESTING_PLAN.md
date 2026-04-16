# ctx Testing Plan

**Version:** 2.0
**Date:** April 16, 2026
**Status:** Active

## Scope

`ctx` is a personal-use Python CLI tool. The testing strategy prioritizes:
- Catching regressions in core logic (chunking, extraction, pack pipeline)
- Verifying CLI commands work end-to-end
- Keeping tests fast and easy to run locally

This is not a team project with QA engineers or multi-platform CI matrices. Tests should be simple, focused, and low-maintenance.

---

## Current Coverage

Existing tests (`tests/`):

| Test File | Lines | What it covers |
|-----------|-------|----------------|
| `test_pack.py` | 1152 | Pack pipeline (scanner, extraction, strategy, inference, chunking) |
| `test_boxnote.py` | 413 | Box Notes ProseMirror extraction |
| `test_extractors.py` | 291 | PDF, PPTX, URL, Markdown extractors |
| `test_claude_code.py` | 205 | Claude Code integration (symlinks, CLAUDE.md patching) |
| `test_definition_chunker.py` | 143 | Definition chunker (H3/H4, bold detection) |
| `test_chunker.py` | 135 | Heading and fixed chunkers |
| `test_git.py` | 120 | Git URL parsing and clone/cache |
| `test_freshness.py` | 113 | Hash computation, build metadata, freshness checks |
| `test_deps.py` | 53 | Dependency parsing and validation |
| `test_module.py` | 52 | Module loading and content file resolution |

**Total: ~2,700 lines across 10 test files.**

### Gaps

1. **CLI commands** — No tests for `cli.py`. All commands (`init`, `create`, `build`, `chunks`, `add`, `remove`, `extract`, `sync`, `pack`, `validate`, `list`) are untested via the CLI entry point.
2. **Schema validation** — Pydantic models in `schema.py` are only tested indirectly through module/pack tests. No direct tests for edge cases (bad versions, invalid strategies, malformed sources).
3. **Error paths** — Limited testing of what happens when things go wrong (missing files, bad YAML, unsupported formats).

---

## What to Add

### Priority 1: CLI Tests

The biggest gap. Use Click's `CliRunner` to invoke commands and check exit codes + output.

**File:** `tests/test_cli.py`

Key tests:
- `ctx init` creates `.context/config.yaml`
- `ctx init` fails if config already exists
- `ctx create my-module` scaffolds correct structure
- `ctx chunks ./module` outputs valid JSONL
- `ctx chunks ./module -f text` outputs human-readable text
- `ctx validate ./module` passes for valid module
- `ctx validate ./bad-module` fails with clear error
- `ctx build` produces JSONL in `.context/chunks/`
- `ctx build --force` rebuilds even when unchanged
- `ctx pack ./dir` outputs JSONL to stdout
- `ctx pack ./dir -o ./out` writes module directory

### Priority 2: Schema Edge Cases

**File:** `tests/test_schema.py`

Key tests:
- `ModuleConfig` accepts minimal valid config (name + version + description)
- `ModuleConfig` applies default chunking values
- `ModuleConfig` rejects missing required fields
- `ModuleConfig` rejects invalid chunking strategy
- `ProjectConfig` accepts path and git module refs
- `ProjectConfig` rejects invalid module ref format

### Priority 3: Error Handling

Sprinkle into existing test files rather than a separate file:
- `load_module()` on nonexistent directory raises `FileNotFoundError`
- `load_module()` on directory without `module.yaml` raises `FileNotFoundError`
- `get_extractor()` on unsupported format raises `ValueError`
- Malformed `module.yaml` raises during validation

---

## What NOT to Add

- **Performance tests** — Not needed at this scale. If chunking a large file gets slow, you'll notice.
- **Cross-platform CI matrix** — Personal project on macOS. No need for Windows/Linux matrices.
- **Multi-Python-version testing** — Target is `>=3.11` per `pyproject.toml`. Test on whatever you have.
- **Coverage thresholds** — Useful for teams, overhead for personal use. Run `--cov` occasionally to spot gaps.
- **Pre-commit hooks running tests** — Too slow for the feedback loop. Just run `pytest` before committing if you want.
- **Docker test environments** — Overkill.
- **Test directory restructure** — The flat `tests/` layout works fine at 10-15 test files.

---

## Running Tests

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_cli.py

# Run with coverage (occasional check)
pytest --cov=src/ctx --cov-report=term-missing

# Run a single test
pytest tests/test_cli.py::test_cli_init_creates_config -v
```

These commands are already in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

No additional pytest config is needed.

---

## CI/CD

A single GitHub Actions workflow is sufficient:

**File:** `.github/workflows/test.yml`

```yaml
name: Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: |
          sudo apt-get update && sudo apt-get install -y poppler-utils
      - run: pip install uv && uv sync --all-extras
      - run: pytest
```

That's it. Add coverage reporting later if you want.
