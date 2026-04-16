# Testing Plan Summary

**Date:** April 16, 2026

## What Exists

10 test files with ~2,700 lines covering: pack pipeline, extractors (PDF, PPTX, URL, Markdown, Box Notes), chunkers (heading, fixed, definition), Claude Code integration, git integration, freshness tracking, dependencies, and module loading.

## What's Missing

1. **CLI tests** — No tests for any of the 11 Click commands in `cli.py`
2. **Schema validation** — No direct tests for Pydantic model edge cases
3. **Error paths** — Limited coverage of failure modes

## Plan

| Priority | What | File | Effort |
|----------|------|------|--------|
| 1 | CLI command tests | `tests/test_cli.py` | ~150 lines |
| 2 | Schema edge case tests | `tests/test_schema.py` | ~80 lines |
| 3 | Error handling additions | Existing test files | ~30 lines |

## Not Doing

- Test directory restructure (flat layout is fine)
- Multi-platform CI matrix (personal macOS project)
- Multi-Python-version testing (targets >=3.11)
- Performance/benchmark tests
- Coverage thresholds or badges
- Pre-commit test hooks
- Docker test environments
- Separate pytest.ini (config stays in pyproject.toml)

## Docs

| File | What |
|------|------|
| [TESTING_PLAN.md](./TESTING_PLAN.md) | Strategy, gaps, what to add and skip |
| [TEST_SPECIFICATIONS.md](./TEST_SPECIFICATIONS.md) | Test case tables per component |
| [SAMPLE_TESTS.md](./SAMPLE_TESTS.md) | Copy-pasteable test implementations |
| [PYTEST_CONFIG.md](./PYTEST_CONFIG.md) | Config and useful commands |
| [CI_CD_CONFIG.md](./CI_CD_CONFIG.md) | GitHub Actions workflow |
| [README.md](./README.md) | Quick reference |
