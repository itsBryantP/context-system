# ctx — Context Module System

## What This Project Is

`ctx` is a Python CLI tool (`ctx-modules` package) for authoring and consuming **context modules** — portable units of knowledge with two output targets:

1. **RAG pipelines** — chunked JSONL with structured metadata, ingestible by any vector store
2. **AI coding tools** — native integration with Bob Shell, Claude Code, Cursor, Copilot, and Continue

Full spec: `specs/BOB_SPEC.md` | Active plans: `plans/active/` | Usage guide: `README.md`

---

## Gantry Workflow

This project uses **Gantry** as its coordination layer. Gantry helps agents work together through:

### Workstream Tokens

Canonical tokens defined in `docs/dev/workstreams.yaml` identify logical work areas:
- `extractor/docx` — Word document extraction
- `chunker/quality` — Chunking improvements
- `integration/bob` — Bob Shell integration
- `docs/spec` — Feature specifications

Use tokens in:
- **Branches**: `feat/extractor/docx-support`
- **Commits**: `feat(extractor/docx): add profile icon filtering`
- **Issues/PRs**: Apply `workstream:extractor/docx` label

### Quality Gates

Before merging, verify:
1. **tests_pass** — `pytest` succeeds
2. **test_coverage** — `pytest --cov=src/ctx --cov-fail-under=90` passes
3. **docs_updated** — AGENTS.md and CLAUDE.md stay in sync
4. **spec_exists** — New features have specs in `specs/features/`

### Roles

- **feature_developer** — Implements features, writes tests, updates docs
- **bug_fixer** — Fixes bugs, adds regression tests
- **documenter** — Updates documentation and specs
- **integrator** — Adds tool integrations (Bob, Claude, etc.)

### Semantic IDs

Commits use conventional format: `<type>(<workstream>): <description>`
- `feat(extractor/docx): add Docling-based extraction`
- `fix(chunker/heading): eliminate orphan headings`
- `docs(spec): add DOCX support specification`

**Migration**: Existing issues/PRs without workstream labels require manual review before backfill. Use `gantry` commands to suggest tokens based on file paths.

---

## Implementation Status

| Phase | Status |
|-------|--------|
| 1 — Core | ✅ Complete — schema, config, module loader, chunkers, JSONL writer, CLI |
| 2 — Extractors | ✅ Complete — PDF, PPTX, URL, Markdown, Box Notes extraction |
| 3 — Claude Code | ✅ Complete — skills, rules, CLAUDE.md integration |
| 4 — Polish | ✅ Complete — definition chunker, dependencies, freshness, git URLs |
| 5 — Pack | ✅ Complete — zero-config packaging |
| 6 — Bob Shell | ✅ Complete — modes, tools, BOB.md, MCP servers, auto-detection, CLI integration |
| 7 — Chunking quality | ✅ Complete — FixedChunker oversized-paragraph fix, orphan elimination, hierarchical-retrieval metadata, opt-in Contextual Retrieval |

---

## Project Layout

```
src/ctx/
├── cli.py                  # Click CLI commands
├── pack.py                 # ctx pack pipeline
├── schema.py               # Pydantic models
├── config.py               # Config management
├── module.py               # Module loading
├── chunker/                # Chunking strategies
├── extractors/             # Content extraction
├── deps.py                 # Dependency validation
├── freshness.py            # Build metadata
├── git.py                  # Git URL modules
└── integrations/           # Tool integrations
tests/                      # Test suite (14 files)
specs/features/             # Feature specifications
plans/active/               # Active development plans
docs/dev/                   # Developer documentation
```

---

## Development Setup

```bash
uv sync                        # install deps + dev extras
uv pip install -e ".[dev]"     # editable install
```

## Running Tests

```bash
pytest                         # run all tests
pytest tests/test_chunker.py   # specific file
pytest -v                      # verbose
pytest --cov=src/ctx --cov-report=term-missing --cov-fail-under=90  # coverage
```

Tests are isolated via `tests/conftest.py` (monkeypatches `Path.home()` per test).

## Running the CLI

```bash
ctx --help
ctx create my-module                        # scaffold new module
ctx pack ./my-docs/                         # zero-config packaging
ctx pack ./my-docs/ --install --tool bob    # install for Bob Shell
ctx build                                   # build all modules
ctx validate ./my-module                    # validate structure
```

---

## Key Conventions

### Chunk IDs
Deterministic: `{module}/{file-stem}/{section-slug}`. Same content → same ID (enables incremental RAG updates).

### Tokenization
Uses `tiktoken` with `cl100k_base` encoding. Token counts pre-computed at build time.

### Git URL Modules
`ModuleRef` supports `git:` URLs in `.context/config.yaml`:
```yaml
modules:
  - git: https://github.com/org/repo.git#subdir@v1.0
```
Repos cached in `~/.ctx/cache/<hash>/`.

### Freshness Tracking
`ctx build` hashes `content/` files (SHA-256), skips unchanged modules. Metadata in `.context/.build-meta.json`. Use `--force` to bypass.

### Supported File Types

| Extension | Classification | Notes |
|-----------|---------------|-------|
| `.md`, `.markdown` | `markdown` | Frontmatter stripped |
| `.txt` | `plaintext` | Filename → H1 heading |
| `.pdf` | `pdf` | pdftotext → PyMuPDF fallback |
| `.pptx` | `pptx` | python-pptx |
| `.docx`, `.docm` | `docx` | Docling conversion, configurable image filtering |
| `.boxnote` | `boxnote` | Box Notes (ProseMirror JSON) |
| `.html`, `.htm` | `html` | markdownify |
| `.yaml`, `.yml`, `.json` | `structured` | Fenced code block |

### Module Schema
Validated by `ModuleConfig` in `schema.py`. Required: `name`, `version`, `description`. Chunking defaults: `heading` strategy, H2 level, 500 max tokens, 50 overlap.

### Project Config
Validated by `ProjectConfig`. Modules via `path:` (local) or `git:` (remote). JSONL output: `.context/chunks/`.

---

## Tool Integration

### Bob Shell
Auto-detected when `.bob/` exists. Installation:
```bash
ctx add ./my-module --tool bob
```
Installs: BOB.md, modes, tools, MCP servers, skills.

### Claude Code
Auto-detected when `.claude/` exists. Installation:
```bash
ctx add ./my-module --tool claude
```
Installs: CLAUDE.md, skills, rules.

### Cross-Framework
Skills in `skills/<name>/SKILL.md` symlink to both `.bob/skills/` and `.claude/skills/` — no duplication.

---

## Configuration Sync

**AGENTS.md and CLAUDE.md must stay in sync.** When updating project structure, tooling, or conventions:

| Change | Update |
|--------|--------|
| New CLI command, chunker, extractor | Both files — Project Layout, Key Conventions |
| Phase milestone | Both files — Implementation Status |
| New dependency | Both files — Dependencies table |
| New tool integration | Both files — Integration sections |
| New safe command | `.claude/settings.json` — add to `allow` |
| New destructive command | `.claude/settings.json` — add to `deny` |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `pydantic` | Schema validation |
| `pyyaml` | YAML parsing |
| `tiktoken` | Token counting (cl100k_base) |
| `pymupdf` | PDF extraction |
| `python-pptx` | PPTX extraction |
| `markdownify` | HTML extraction |
| `docling` | DOCX extraction |
| `pytest` | Test runner (dev) |
| `anthropic` | Contextual Retrieval (optional: `contextualize`) |

---

## Resources

- **Specifications**: `specs/BOB_SPEC.md`, `specs/features/`
- **Plans**: `plans/active/` (in-flight), `plans/archive/` (completed)
- **Prompts**: `prompts/` (reusable evaluation prompts)
- **Workstreams**: `docs/dev/workstreams.yaml` (canonical tokens)
- **Gantry Config**: `gantry.yaml` (quality gates, roles, workflows)

---

## Gantry Commands

```bash
# Validate workstream manifest
gantry skill validate

# Build skills from workstreams
gantry skill build

# Install/update OpenCode plugin
gantry opencode install-plugin [--force]

# Check project status
gantry status
```

After upgrading Gantry configuration, run:
```bash
gantry skill build && gantry skill validate && pytest
```
