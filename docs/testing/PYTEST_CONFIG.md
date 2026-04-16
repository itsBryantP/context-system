# pytest Configuration

## Current Config

All config lives in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

That's all that's needed. pytest discovers `test_*.py` files in `tests/` by default.

## Optional Additions

If you want coverage checking on every run, add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src/ctx --cov-report=term-missing --tb=short"
```

If you add markers later:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: tests that take >5s",
]
```

Then skip them with `pytest -m "not slow"`.

## Dev Dependencies

Already in `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
```

Install with: `uv sync` or `uv pip install -e ".[dev]"`

## Useful Commands

```bash
pytest                                    # run all
pytest tests/test_cli.py                  # one file
pytest tests/test_cli.py::TestInit        # one class
pytest tests/test_cli.py::TestInit::test_creates_config  # one test
pytest -k "pack"                          # name pattern
pytest -x                                 # stop on first failure
pytest -v                                 # verbose
pytest --cov=src/ctx --cov-report=html    # HTML coverage report
pytest --tb=long                          # full tracebacks
pytest -s                                 # show print output
```
