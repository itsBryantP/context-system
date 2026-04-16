# CI/CD Configuration

## GitHub Actions

A single workflow for running tests on push/PR:

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
      - name: Install system deps
        run: sudo apt-get update && sudo apt-get install -y poppler-utils
      - name: Install project
        run: pip install uv && uv sync --all-extras
      - name: Run tests
        run: pytest
```

That's it. Add coverage reporting or matrix builds later if needed.
