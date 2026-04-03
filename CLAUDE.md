# ctx — Context Module System

## What This Project Is

`ctx` is a Python CLI tool (`ctx-modules` package) for authoring and consuming **context modules** — portable units of knowledge with two output targets:

1. **RAG pipelines** — chunked JSONL with structured metadata, ingestible by any vector store
2. **AI coding tools** — native Claude Code integration (skills, rules, CLAUDE.md imports), extensible to Cursor, Copilot, etc.

Full spec: `SPEC.md` | Usage guide + examples: `README.md`

---

## Implementation Status

All phases complete. The project is feature-complete per the original spec plus the `ctx pack` extension.

| Phase | What was delivered |
|-------|--------------------|
| 1 — Core | schema, config, module loader, chunkers (heading + fixed), JSONL writer, CLI |
| 2 — Extractors | PDF, PPTX, URL, Markdown → content/; `ctx extract` and `ctx sync` |
| 3 — Claude Code | `ctx add` / `ctx remove` — skill/rule symlinks, CLAUDE.md patching |
| 4 — Polish | definition chunker, dependency resolution, freshness tracking, git URLs, --tool flag |
| 5 — Pack | `ctx pack` — zero-config packaging: scan, extract, auto-detect strategy/name/tags, chunk, output |

---

## Project Layout

```
src/ctx/
├── cli.py                  # Click CLI: init, create, build, chunks, list, validate, extract, sync, pack
├── pack.py                 # ctx pack pipeline: scan_directory, extract_files, select_strategy, infer_*, chunk_files, write_module, pack
├── schema.py               # Pydantic models for module.yaml and .context/config.yaml
├── config.py               # Load/save .context/config.yaml
├── module.py               # Module loading, validation, content file resolution
├── chunker/
│   ├── base.py             # ChunkStrategy ABC and Chunk dataclass
│   ├── heading.py          # Heading-based semantic chunking (default)
│   ├── fixed.py            # Fixed token-size sliding window
│   └── definition.py       # One chunk per term; H3/H4 or **Bold**: detection, grouping
├── extractors/
│   ├── __init__.py         # Registry — get_extractor(source) dispatcher
│   ├── base.py             # Extractor ABC
│   ├── markdown.py         # Passthrough copy with frontmatter stripping
│   ├── pdf.py              # pdftotext (poppler) primary, PyMuPDF fallback
│   ├── pptx.py             # python-pptx; slides → ## Slide N, notes → blockquotes
│   └── url.py              # urllib fetch + markdownify; stores fetched_at frontmatter
├── deps.py                 # parse_dep / check_dependencies — depends_on validation
├── freshness.py            # compute_module_hash, build metadata, is_fresh / record_build
├── git.py                  # parse_git_ref, resolve_git_module — clone/cache git modules
└── integrations/
    ├── jsonl.py            # JSONL serialization and file writing
    └── claude_code.py      # install_module / remove_module — symlinks, CLAUDE.md, cross-tool files
tests/
├── test_chunker.py
├── test_definition_chunker.py
├── test_extractors.py
├── test_claude_code.py
├── test_deps.py
├── test_freshness.py
├── test_git.py
├── test_module.py
└── fixtures/sample-module/ # Minimal valid module for testing
```

---

## Development Setup

```bash
uv sync                        # install deps + dev extras
uv pip install -e ".[dev]"     # editable install with dev deps
```

## Running Tests

```bash
pytest                         # run all tests
pytest tests/test_chunker.py   # specific file
pytest -v                      # verbose
```

## Running the CLI

```bash
ctx --help
ctx create my-module                        # scaffold a new module
ctx chunks ./my-module                      # stream JSONL to stdout
ctx chunks ./my-module -f text              # human-readable output
ctx init                                    # create .context/config.yaml in cwd
ctx build                                   # build all modules (skips unchanged)
ctx build --force                           # rebuild even if content unchanged
ctx validate ./my-module                    # validate module structure
ctx add ./my-module                         # install module (auto-detects tools)
ctx add ./my-module --tool cursor --tool claude  # install for specific tools
ctx remove my-module-name                   # remove module by name
ctx extract spec.pdf --into ./my-module     # ingest a source file
ctx sync ./my-module                        # re-extract all sources in module.yaml
ctx pack ./my-docs/                         # zero-config: scan dir → JSONL stdout
ctx pack ./my-docs/ -o ./my-module          # write a full module directory
ctx pack ./my-docs/ --install               # install directly into project
ctx pack ./my-docs/ -f text                 # human-readable chunk preview
```

---

## Key Conventions

### Chunk IDs
Deterministic and hierarchical: `{module}/{file-stem}/{section-slug}`. Same content always produces the same ID — enables incremental RAG updates.

### Tokenization
Uses `tiktoken` with `cl100k_base` encoding. All token counts are pre-computed at build time and stored in chunk metadata.

### Git URL modules
`ModuleRef` supports `git:` in addition to `path:` in `.context/config.yaml`:
```yaml
modules:
  - git: https://github.com/org/repo.git#subdir@v1.0
```
Repos are cloned once to `~/.ctx/cache/<hash>/` and reused. Format: `repo[#subdir][@ref]`.

### Freshness tracking
`ctx build` hashes each module's `content/` files (SHA-256) and skips modules whose hash hasn't changed since the last build. Metadata stored in `.context/.build-meta.json`. Use `--force` to bypass.

### Dependency warnings
Modules declare `depends_on: [module-name@version]` in `module.yaml`. `ctx build` emits a warning (not error) for any unmet dependencies. Version constraints are recorded but not enforced yet.

### Cross-framework tool files
`ctx add --tool cursor|copilot|continue` symlinks tool-specific files (`.cursorrules`, `COPILOT.md`, `.continuerules`) from the module to the project root. Without `--tool`, auto-detects based on project structure (`.cursor/`, `.github/`, `.continuerules`).

### Module Schema (module.yaml)
Validated by `ModuleConfig` Pydantic model in `schema.py`. Required fields: `name`, `version`, `description`. Chunking defaults to `heading` strategy at H2 level, 500 max tokens, 50 overlap.

### Project Config (.context/config.yaml)
Validated by `ProjectConfig`. Modules referenced by `path:` (local) or `git:` (remote). JSONL output goes to `.context/chunks/` (gitignore in consuming projects).

### Adding a New Chunker
1. Subclass `ChunkStrategy` in `chunker/base.py`
2. Implement `chunk(content, *, module_name, source_file, tags, version, max_tokens, overlap_tokens, **kwargs) -> list[Chunk]`
3. Add a new `ChunkingStrategy` enum value in `schema.py`
4. Wire it up in `cli.py:_get_chunker()`

### Adding an Extractor
Subclass `Extractor` from `extractors/base.py` and register it in `extractors/__init__.py`:
```python
def can_handle(self, source: Source) -> bool: ...
def extract(self, source: Source, output_dir: Path) -> list[Path]: ...
```
Add an instance to `_REGISTRY` in `extractors/__init__.py`. Order matters — first match wins.

### ctx pack pipeline (`pack.py`)
The pack pipeline is a pure-function chain — each step is independently testable:

```
scan_directory(input_dir)
  → list[ScanResult]                       # classified file paths
  → extract_files(results, input_dir, tmp) # → list[ExtractedFile], failures
  → build_strategy_map(extracted)          # → dict[Path, ChunkingStrategy]
  → infer_name / infer_description / infer_tags
  → chunk_files(extracted, strategies, ...) # → list[Chunk]
  → write_module / pack (output modes)
```

To support a new file type in `ctx pack`:
1. Add the extension to `_EXT_MAP` in `pack.py` with a classification string
2. Add a handler `_extract_<classification>(src, out) -> Path` in `pack.py`
3. Wire it in `_extract_one()`
4. Update `_CLS_TO_SOURCE_TYPE` if there's a matching `SourceType`

---

## Keeping Configuration Current

When you make or observe changes that affect project structure, tooling, or conventions, update the relevant config files in the same session — don't defer it:

| Change | Update |
|--------|--------|
| New CLI command, chunker, extractor, or integration | `CLAUDE.md` — Project Layout, Key Conventions |
| Phase milestone reached (e.g. Phase 2 complete) | `CLAUDE.md` — Current State table |
| New dev dependency or optional extra added to `pyproject.toml` | `CLAUDE.md` — Dependencies table |
| New safe command needed (e.g. new test runner, linter) | `.claude/settings.json` — add to `allow` |
| New destructive command identified | `.claude/settings.json` — add to `deny` |
| New environment constraint (Python version bump, new tool in use) | both files |

The goal is that `CLAUDE.md` and `.claude/settings.json` always reflect the current state of the project — not a snapshot from when they were first written.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `pydantic` | Schema validation for module.yaml and config.yaml |
| `pyyaml` | YAML parsing |
| `tiktoken` | Token counting (cl100k_base) |
| `pytest` | Test runner (dev) |
| `pymupdf`, `python-pptx`, `markdownify` | Optional — Phase 2 extractors |
