# ctx Testing

## Running Tests

```bash
pytest                          # run everything
pytest tests/test_cli.py        # one file
pytest -k "test_chunker" -v     # by name pattern
pytest --cov=src/ctx            # with coverage report
```

## Test Files

| File | What it tests |
|------|---------------|
| `test_pack.py` | Pack pipeline (scan, extract, strategy, inference, chunk, output) |
| `test_boxnote.py` | Box Notes ProseMirror JSON extraction |
| `test_extractors.py` | PDF, PPTX, URL, Markdown extractors |
| `test_claude_code.py` | Claude Code integration (symlinks, CLAUDE.md patching) |
| `test_definition_chunker.py` | Definition chunker (H3/H4, bold term detection) |
| `test_chunker.py` | Heading and fixed chunkers |
| `test_git.py` | Git URL parsing, clone, cache |
| `test_freshness.py` | Content hashing, build metadata, freshness |
| `test_deps.py` | Dependency parsing and checking |
| `test_module.py` | Module loading, content file resolution |
| `test_cli.py` | CLI commands (init, create, chunks, pack, etc.) |
| `test_schema.py` | Pydantic model validation edge cases |

## Writing Tests

Tests live in `tests/` as flat files. Use `tmp_path` (pytest built-in) for temp directories. For CLI tests, use Click's `CliRunner`:

```python
from click.testing import CliRunner
from ctx.cli import cli

def test_something(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["chunks", str(tmp_path / "module")])
    assert result.exit_code == 0
```

The sample module at `tests/fixtures/sample-module/` is available for any test that needs a valid module.

## Docs

- [TESTING_PLAN.md](./TESTING_PLAN.md) — Strategy, gaps, priorities
- [TEST_SPECIFICATIONS.md](./TEST_SPECIFICATIONS.md) — Test case tables
- [SAMPLE_TESTS.md](./SAMPLE_TESTS.md) — Copy-pasteable test code
