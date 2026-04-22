# ctx — Context Module System

## What This Project Is

`ctx` is a Python CLI tool (`ctx-modules` package) for authoring and consuming **context modules** — portable units of knowledge with two output targets:

1. **RAG pipelines** — chunked JSONL with structured metadata, ingestible by any vector store
2. **AI coding tools** — native integration with Bob Shell, Claude Code, Cursor, Copilot, and Continue

Full spec: `specs/BOB_SPEC.md` | Active plans: `plans/active/` (Bob Shell, chunking improvements) | Usage guide: `README.md`

---

## Implementation Status

Bob Shell integration is planned. Core system is feature-complete.

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
├── cli.py                  # Click CLI: init, create, build, chunks, list, validate, extract, sync, pack, add, remove
├── pack.py                 # ctx pack pipeline: scan, extract, auto-detect, chunk, output
├── schema.py               # Pydantic models for module.yaml and .context/config.yaml
├── config.py               # Load/save .context/config.yaml
├── module.py               # Module loading, validation, content file resolution
├── chunker/
│   ├── base.py             # ChunkStrategy ABC, Chunk dataclass, metadata helpers
│   ├── heading.py          # Heading-based semantic chunking (default); orphan filter
│   ├── fixed.py            # Fixed token-size sliding window; oversized splitter
│   ├── definition.py       # One chunk per term; H3/H4 or **Bold**: detection
│   └── contextualize.py    # Optional Contextual Retrieval (Anthropic) — opt-in
├── extractors/
│   ├── __init__.py         # Registry — get_extractor(source) dispatcher
│   ├── base.py             # Extractor ABC
│   ├── markdown.py         # Passthrough with frontmatter stripping
│   ├── pdf.py              # pdftotext (poppler) primary, PyMuPDF fallback
│   ├── pptx.py             # python-pptx; slides → ## Slide N
│   └── url.py              # urllib fetch + markdownify
├── deps.py                 # Dependency validation — depends_on checking
├── freshness.py            # Build metadata, hash-based skip logic
├── git.py                  # Git URL module resolution — clone/cache
└── integrations/
    ├── jsonl.py            # JSONL serialization and file writing
    └── claude_code.py      # Cross-framework integration (Claude, Cursor, Copilot, Continue, Bob)
tests/
├── conftest.py              # Autouse fixture: Path.home() → tmp dir per test (isolation)
├── test_chunker.py
├── test_definition_chunker.py
├── test_extractors.py
├── test_boxnote.py          # .boxnote (ProseMirror JSON) extraction
├── test_claude_code.py
├── test_cli.py              # CLI command tests via CliRunner
├── test_schema.py           # Pydantic model edge-case tests
├── test_pack.py             # ctx pack pipeline
├── test_contextualize.py    # Contextual Retrieval with mocked Anthropic client
├── test_bob_integration.py  # Planned — Bob Shell integration tests
├── test_deps.py
├── test_freshness.py
├── test_git.py
├── test_module.py
└── fixtures/
    ├── sample-module/       # Minimal valid module
    └── bob-test-module/     # Planned — Bob Shell test module
.github/workflows/test.yml   # CI — push/PR to main, Ubuntu, uv sync + pytest
docs/testing/                # Testing strategy, specs, pytest config, CI workflow
plans/
├── active/                  # In-flight plans (BOB_PLAN.md)
└── archive/                 # Completed (PACK_PLAN.md, CHUNKING_IMPROVEMENTS_PLAN.md)
specs/features/              # Per-feature specs (PACK, CHUNKER_*, CONTEXTUAL_RETRIEVAL)
prompts/                     # Reusable prompts (chunking-evaluation, testing-plan)
```

---

## Bob Shell Integration

### Architecture

Bob Shell uses:
- **Modes** — Specialized interaction contexts (`.bob/modes/*.yaml`)
- **Tools** — Custom capabilities (`.bob/tools/*.yaml`)
- **MCP Servers** — Model Context Protocol servers (`.bob/servers/*.json`)
- **BOB.md** — Context file (like CLAUDE.md)

### Module Structure for Bob Shell

```
api-patterns/
├── module.yaml              # ctx module configuration
├── content/                 # Markdown content for RAG
│   ├── overview.md
│   └── patterns.md
├── BOB.md                   # Bob Shell context
└── bob/                     # Bob Shell integration
    ├── modes/               # Custom modes
    │   └── api-review.yaml
    ├── tools/               # Custom tools
    │   └── search-pattern.yaml
    └── servers/             # MCP servers
        └── kb.json
```

### Installation

```bash
# Auto-detect tools (includes Bob if .bob/ exists)
ctx add ~/modules/api-patterns

# Explicit Bob Shell installation
ctx add ~/modules/api-patterns --tool bob

# Multi-tool installation
ctx add ~/modules/api-patterns --tool claude --tool bob
```

### What Gets Installed

When installing for Bob Shell:
1. **BOB.md** → symlinked to project root (or import appended if exists)
2. **Modes** → `bob/modes/*.yaml` → `.bob/modes/`
3. **Tools** → `bob/tools/*.yaml` → `.bob/tools/`
4. **MCP Servers** → `bob/servers/*.json` → `.bob/servers/`

### Detection Heuristics

Bob Shell is auto-detected when:
- `.bob/` directory exists in project root
- `BOB.md` file exists in project root

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
pytest tests/test_bob_integration.py  # Bob Shell tests (when implemented)
pytest -v                      # verbose
```

Tests are isolated from the user's home directory via `tests/conftest.py`
(monkeypatches `Path.home()` per test). `src/ctx/git.py` caches cloned modules
under `~/.ctx/cache/` — the fixture prevents any test from writing there, even
on accidental code paths. Verify post-run: `ls ~/.ctx` should still fail.

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
ctx pack ./my-docs/ --tool bob              # install for Bob Shell
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

### Supported file types in `ctx pack`

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

### Cross-framework tool files
`ctx add --tool bob|cursor|copilot|continue` symlinks tool-specific files from the module to the project. Without `--tool`, auto-detects based on project structure.

### Bob Shell Modes
Modes define specialized interaction contexts with:
- Tool access control
- Context sources (files, chunks, directories)
- System prompts
- File restrictions
- Behavioral settings

Example mode (`bob/modes/api-review.yaml`):
```yaml
name: API Review
slug: api-review
icon: 🔍
tools:
  - read_file
  - search_file_content
context:
  - type: file
    path: BOB.md
  - type: chunks
    source: .context/chunks/api-patterns.jsonl
prompts:
  system: |
    Review API code against documented patterns.
file_restrictions:
  allow_patterns:
    - "src/api/**/*.ts"
```

### Bob Shell Tools
Tools extend Bob's capabilities with:
- Parameters (typed, validated)
- Implementation (script, MCP, Python, Node)
- Execution settings (timeout, cache, retry)
- Permissions (file access, command execution)

Example tool (`bob/tools/search-pattern.yaml`):
```yaml
name: search-pattern
description: Search API patterns knowledge base
category: knowledge
parameters:
  - name: query
    type: string
    required: true
implementation:
  type: script
  command: |
    cat .context/chunks/api-patterns.jsonl | \
    python3 -c "..." "$query"
permissions:
  read_files:
    - ".context/chunks/*.jsonl"
```

### Bob Shell MCP Servers
MCP servers provide advanced capabilities:
- Tools and resources
- Lifecycle management
- Environment configuration

Example server (`bob/servers/kb.json`):
```json
{
  "name": "api-patterns-kb",
  "description": "API Patterns Knowledge Base",
  "type": "stdio",
  "command": "python",
  "args": ["-m", "ctx.mcp.knowledge_server", "--chunks", ".context/chunks/api-patterns.jsonl"],
  "capabilities": {
    "tools": true,
    "resources": true
  }
}
```

### Module Schema (module.yaml)
Validated by `ModuleConfig` Pydantic model in `schema.py`. Required fields: `name`, `version`, `description`. Chunking defaults to `heading` strategy at H2 level, 500 max tokens, 50 overlap.

### Project Config (.context/config.yaml)
Validated by `ProjectConfig`. Modules referenced by `path:` (local) or `git:` (remote). JSONL output goes to `.context/chunks/` (gitignore in consuming projects).

---

## Adding Bob Shell Support to a Module

### 1. Create BOB.md

```markdown
# API Patterns Module

This module provides REST API design patterns and conventions.

## Usage with Bob Shell

Use the `api-review` mode to review API implementations against these patterns.

## Key Concepts

- RESTful resource naming
- Authentication patterns
- Error handling standards
```

### 2. Create Modes (Optional)

Create `bob/modes/api-review.yaml` with mode configuration.

### 3. Create Tools (Optional)

Create `bob/tools/search-pattern.yaml` with tool configuration.

### 4. Create MCP Servers (Optional)

Create `bob/servers/kb.json` with server configuration.

### 5. Install

```bash
ctx add ./my-module --tool bob
```

---

## Keeping Configuration Current

When you make or observe changes that affect project structure, tooling, or conventions, update the relevant config files in the same session:

| Change | Update |
|--------|--------|
| New CLI command, chunker, extractor, or integration | `AGENTS.md` — Project Layout, Key Conventions |
| Phase milestone reached | `AGENTS.md` — Implementation Status table |
| New dev dependency or optional extra | `AGENTS.md` — Dependencies table |
| New Bob Shell feature implemented | `AGENTS.md` — Bob Shell Integration section |
| New environment constraint | Update all relevant docs |

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
| `anthropic` | Contextual Retrieval (optional extra: `contextualize`) |

---

## Bob Shell Resources

- **Specification**: `specs/BOB_SPEC.md` — Complete Bob Shell integration specification
- **Implementation Plan**: `plans/active/BOB_PLAN.md` — Detailed implementation roadmap
- **Examples**: See `specs/BOB_SPEC.md` for complete examples of modes, tools, and MCP servers

## Chunking Quality (Phase 7) — Implemented

Four-phase rollout, driven by the evaluation in `prompts/chunking-evaluation-prompt.md`. All four phases shipped; the plan has moved to `plans/archive/`.

| Phase | Change | Spec |
|-------|--------|------|
| 1 | `FixedChunker` oversized-paragraph splitter — every chunk now ≤ `max_tokens` | `specs/features/CHUNKER_OVERSIZED_FIX_SPEC.md` |
| 2 | `HeadingChunker` orphan-heading elimination — zero title-only chunks on real corpora | `specs/features/CHUNKER_ORPHAN_ELIMINATION_SPEC.md` |
| 3 | Hierarchical-retrieval metadata — `doc_title`, `file_id`, `has_code`, `language`, `prev_chunk_id`, `next_chunk_id` on every chunk | `specs/features/CHUNKER_METADATA_SPEC.md` |
| 4 | Opt-in Contextual Retrieval via `chunking.contextualize: true` — lazy Anthropic import, content-addressed cache at `.context/.contextualize-cache.json` | `specs/features/CONTEXTUAL_RETRIEVAL_SPEC.md` |

Rollout check on the zconfig/docs reference corpus: `chunks 147 → 139`, `max_tok 1559 → 500`, `orphans 15 → 0`.
