# ctx — Context Module System

## What This Project Is

`ctx` is a Python CLI tool (`ctx-modules` package) for authoring and consuming **context modules** — portable units of knowledge with two output targets:

1. **RAG pipelines** — chunked JSONL with structured metadata, ingestible by any vector store
2. **AI coding tools** — native integration with Bob Shell, Claude Code, Cursor, Copilot, and Continue

Full spec: `SPEC.md` | Usage guide + examples: `README.md`

---

## Implementation Status

| Phase | What was delivered |
|-------|--------------------|
| 1 — Core | schema, config, module loader, chunkers (heading + fixed), JSONL writer, CLI |
| 2 — Extractors | PDF, PPTX, URL, Markdown → content/; `ctx extract` and `ctx sync` |
| 3 — Claude Code | `ctx add` / `ctx remove` — skill/rule symlinks, CLAUDE.md patching |
| 4 — Polish | definition chunker, dependency resolution, freshness tracking, git URLs, --tool flag |
| 5 — Pack | `ctx pack` — zero-config packaging: scan, extract, auto-detect strategy/name/tags, chunk, output |
| 6 — Bob Shell | ✅ modes, tools, BOB.md, MCP servers, auto-detection, CLI integration |
| 7 — Chunking quality | ✅ FixedChunker oversized-paragraph fix, orphan-chunk elimination, hierarchical-retrieval metadata (`doc_title`, `has_code`, `language`, `prev_chunk_id`, `next_chunk_id`, `file_id`), opt-in Contextual Retrieval |

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
│   ├── base.py             # ChunkStrategy ABC, Chunk dataclass, metadata helpers (detect_code, compute_file_id, apply_chain_metadata)
│   ├── heading.py          # Heading-based semantic chunking (default); orphan-heading filter
│   ├── fixed.py            # Fixed token-size sliding window; oversized-paragraph splitter
│   ├── definition.py       # One chunk per term; H3/H4 or **Bold**: detection, grouping
│   └── contextualize.py    # Optional Contextual Retrieval — LLM-prepended situating context per chunk
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
    └── claude_code.py      # Cross-framework integration (Claude, Cursor, Copilot, Continue, Bob)
tests/
├── conftest.py              # Autouse fixture — redirects Path.home() to a tmp dir per test
├── test_chunker.py
├── test_definition_chunker.py
├── test_extractors.py
├── test_boxnote.py          # .boxnote (ProseMirror JSON) extraction tests
├── test_claude_code.py
├── test_cli.py              # CLI command tests (CliRunner against ctx.cli:cli)
├── test_schema.py           # Pydantic model edge-case tests
├── test_pack.py             # ctx pack pipeline (scan, extract, chunk, output)
├── test_contextualize.py    # Contextual Retrieval — mocked Anthropic client
├── test_bob_integration.py  # Bob Shell integration tests
├── test_deps.py
├── test_freshness.py
├── test_git.py
├── test_module.py
└── fixtures/sample-module/  # Minimal valid module for testing
.github/workflows/test.yml   # CI — push/PR to main, fresh Ubuntu VM, uv sync + pytest
docs/testing/                # Testing strategy, specs, pytest config, CI workflow
plans/
├── active/                  # In-flight work
└── archive/                 # Completed plans (e.g. CHUNKING_IMPROVEMENTS_PLAN.md, PACK_PLAN.md)
specs/features/              # Per-feature specs (PACK_SPEC.md, CHUNKER_*, CONTEXTUAL_RETRIEVAL_SPEC.md)
prompts/                     # Reusable prompts (chunking-evaluation, testing-plan)
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

Tests are fully isolated — `tests/conftest.py` monkeypatches `Path.home()` to a
per-test tmp dir so `src/ctx/git.py`'s `~/.ctx/cache/` writes can never leak
into the real home directory. After a run, `ls ~/.ctx` should still fail with
"No such file or directory".

If the global pytest has broken plugins, use a project-local venv:
```bash
python3 -m venv .venv-test && .venv-test/bin/pip install -e ".[dev,extractors]"
.venv-test/bin/pytest
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
ctx add ./my-module --tool bob              # install for Bob Shell only
ctx add ./my-module --tool claude --tool bob # install for multiple tools
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
`ctx add --tool bob|cursor|copilot|continue` symlinks tool-specific files from the module to the project. Without `--tool`, auto-detects based on project structure.

**Bob Shell**: Installs `BOB.md` (symlinked or appended), modes (`bob/modes/*.yaml` → `.bob/modes/`), tools (`bob/tools/*.yaml` → `.bob/tools/`), and MCP servers (`bob/servers/*.json` → `.bob/servers/`). Auto-detected via `.bob/` directory or `BOB.md` file.

**Claude Code**: Symlinks skills/rules to `.claude/`, patches CLAUDE.md imports.

**Cursor/Copilot/Continue**: Symlinks `.cursorrules`, `COPILOT.md`, `.continuerules` to project root.

### Module Schema (module.yaml)
Validated by `ModuleConfig` Pydantic model in `schema.py`. Only `name` is required (`version` defaults to `"0.1.0"`, `description` to `""`). Chunking defaults to `heading` strategy at H2 level, 500 max tokens, 50 overlap. Optional `chunking.contextualize: true` (with `contextualize_model: "claude-haiku-4-5"`) enables Contextual Retrieval — requires the `contextualize` extra (`uv pip install 'ctx-modules[contextualize]'`) and `ANTHROPIC_API_KEY`.

### Chunk metadata
Every chunk carries a rich metadata dict: `tags`, `version`, `token_count`, `chunk_index`/`total_chunks`, `heading_level`, `parent_section`, `doc_title`, `file_id` (stable sha256 prefix of source path), `has_code` (bool, set iff content contains a complete fenced block), `language` (first-fence info string lowercased), `prev_chunk_id`/`next_chunk_id` (chain within a source file). When contextualize is enabled, `situating_context` and `contextualized: true` are also set. Consumers use these for parent-expansion, code-aware filtering, and doc-level diversification.

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

Supported file types in `ctx pack` (`_EXT_MAP` in `pack.py`):

| Extension | Classification | Notes |
|-----------|---------------|-------|
| `.md`, `.markdown` | `markdown` | Frontmatter stripped |
| `.txt` | `plaintext` | Filename → H1 heading |
| `.pdf` | `pdf` | pdftotext → PyMuPDF fallback |
| `.pptx` | `pptx` | python-pptx |
| `.ppt` | `unsupported` | Legacy binary format; python-pptx requires .pptx |
| `.boxnote` | `boxnote` | Box Notes (ProseMirror JSON) |
| `.html`, `.htm` | `html` | markdownify |
| `.yaml`, `.yml`, `.json` | `structured` | Fenced code block |

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
| `pymupdf` | PDF extraction (core) |
| `python-pptx` | PPTX extraction (core) |
| `markdownify` | HTML extraction (core) |
| `pytest` | Test runner (dev) |
| `anthropic` | Contextual Retrieval LLM calls (optional extra: `contextualize`) |
