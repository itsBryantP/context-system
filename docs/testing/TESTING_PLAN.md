# ctx Testing Plan

**Version:** 2.0
**Date:** April 16, 2026
**Status:** Active

## Scope

`ctx` is a personal-use Python CLI tool. The testing strategy prioritizes:
- Catching regressions in core logic (chunking, extraction, pack pipeline)
- Verifying CLI commands work end-to-end
- Keeping tests fast and easy to run locally
- Full isolation — no test ever writes to `$HOME` or `~/.ctx/cache`

This is not a team project with QA engineers or multi-platform CI matrices. Tests should be simple, focused, and low-maintenance.

## Isolation

`src/ctx/git.py` caches cloned modules under `Path.home() / ".ctx" / "cache"`.
To keep tests from ever touching the real home directory, `tests/conftest.py`
has an autouse fixture that monkeypatches `Path.home()` to a per-test tmp dir.
Combined with the pytest `tmp_path` fixture (which uses `$TMPDIR`, not `$HOME`),
tests can't escape the sandbox.

After running the suite, check that `~/.ctx` still doesn't exist:
```bash
ls ~/.ctx  # should fail with "No such file or directory"
```

---

## Current Coverage

Tests now total **297 passing across 12 files** (~3,000 lines).

| Test File | What it covers |
|-----------|----------------|
| `test_pack.py` | Pack pipeline (scanner, extraction, strategy, inference, chunking) |
| `test_cli.py` | CLI commands — init, create, chunks, validate, build, pack, add/remove, list |
| `test_boxnote.py` | Box Notes ProseMirror extraction |
| `test_extractors.py` | PDF, PPTX, URL, Markdown extractors |
| `test_claude_code.py` | Claude Code integration (symlinks, CLAUDE.md patching) |
| `test_definition_chunker.py` | Definition chunker (H3/H4, bold detection) |
| `test_chunker.py` | Heading and fixed chunkers |
| `test_git.py` | Git URL parsing and clone/cache |
| `test_freshness.py` | Hash computation, build metadata, freshness checks |
| `test_schema.py` | Pydantic model validation edge cases |
| `test_module.py` | Module loading, content file resolution, error paths |
| `test_deps.py` | Dependency parsing and validation |

### Implemented in this plan

1. **`test_cli.py` (19 tests)** — covers init, create, chunks, validate, build (with freshness skip and --force), pack (stdout, -o, existing-output error), add/remove, list.
2. **`test_schema.py` (14 tests)** — direct Pydantic validation for `ModuleConfig`, `ProjectConfig`, `ModuleRef`, `ChunkingConfig`.
3. **`test_module.py` malformed YAML test** — added error path for corrupt `module.yaml`.
4. **`conftest.py`** — autouse fixture that redirects `Path.home()` to a per-test tmp dir.

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
pytest tests/test_cli.py::TestInit::test_creates_config -v
```

These commands are already in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

**If the global pytest has broken plugins** (e.g. pytest-ansible trying to write
to `~/.ansible/tmp/`), use a project-local venv to get a clean environment:

```bash
python3 -m venv .venv-test
.venv-test/bin/pip install -e ".[dev,extractors]"
.venv-test/bin/pytest
```

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
