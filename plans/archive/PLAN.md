# ctx — Implementation Plan

## Phases

### Phase 1: Core (MVP)

**Goal**: Author a module, chunk it, pipe JSONL to any RAG system.

| # | File | What |
|---|------|------|
| 1 | `src/ctx/schema.py` | Pydantic models for module.yaml and config.yaml |
| 2 | `src/ctx/config.py` | Load/save .context/config.yaml |
| 3 | `src/ctx/module.py` | Load, validate, resolve modules from local paths |
| 4 | `src/ctx/chunker/base.py` | ChunkStrategy ABC, Chunk dataclass |
| 5 | `src/ctx/chunker/heading.py` | Heading-based semantic chunking |
| 6 | `src/ctx/chunker/fixed.py` | Fixed token-size window with overlap |
| 7 | `src/ctx/integrations/jsonl.py` | JSONL output writer |
| 8 | `src/ctx/cli.py` | CLI: `init`, `create`, `build`, `chunks`, `list` |
| 9 | `pyproject.toml` | Package config with Click entry point |
| 10 | `tests/` | Unit tests for chunker + module loading |

**Dependencies**: click, pydantic, pyyaml, tiktoken

**Verify**:
```bash
ctx create test-module
# add content to test-module/content/
ctx build
ctx chunks test-module | wc -l
ctx chunks test-module | python3 -m json.tool --json-lines | head -20
```

---

### Phase 2: Extractors

**Goal**: Automated content ingestion from PDFs, PowerPoints, URLs, and markdown.

| # | File | What |
|---|------|------|
| 11 | `src/ctx/extractors/base.py` | Extractor ABC |
| 12 | `src/ctx/extractors/pdf.py` | pdftotext / PyMuPDF extraction |
| 13 | `src/ctx/extractors/pptx.py` | python-pptx extraction |
| 14 | `src/ctx/extractors/markdown.py` | Passthrough with frontmatter parsing |
| 15 | `src/ctx/extractors/url.py` | Fetch + markdownify |
| 16 | CLI additions | `extract`, `sync` commands |

**Optional dependencies**: pymupdf, python-pptx, markdownify

**Verify**:
```bash
ctx extract ~/Documents/spec.pdf --into my-module
ls my-module/content/  # should have spec.md
ctx build
ctx chunks my-module | head -5
```

---

### Phase 3: Claude Code Integration

**Goal**: `ctx add <module>` wires up skills, rules, and CLAUDE.md imports.

| # | File | What |
|---|------|------|
| 17 | `src/ctx/integrations/claude_code.py` | Symlink management, CLAUDE.md patching |
| 18 | CLI additions | `add`, `remove` commands |

**Verify**:
```bash
ctx add ~/context-modules/api-patterns
ls -la .claude/skills/
ls -la .claude/rules/
grep "@" CLAUDE.md
ctx remove api-patterns
# verify cleanup
```

---

### Phase 4: Polish

**Goal**: Production-quality module system.

| # | What |
|---|------|
| 19 | `src/ctx/chunker/definition.py` — glossary/FAQ chunking |
| 20 | Dependency resolution between modules |
| 21 | Freshness tracking (source_hash, last_synced in build metadata) |
| 22 | Git URL module resolution |
| 23 | `--tool` flag for cross-framework install (Cursor, Copilot) |

---

## Package Structure

```
context-system/
├── pyproject.toml
├── README.md
├── SPEC.md
├── PLAN.md
├── src/
│   └── ctx/
│       ├── __init__.py
│       ├── cli.py
│       ├── schema.py
│       ├── config.py
│       ├── module.py
│       ├── chunker/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── heading.py
│       │   ├── fixed.py
│       │   └── definition.py       # Phase 4
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── pdf.py
│       │   ├── pptx.py
│       │   ├── markdown.py
│       │   └── url.py
│       └── integrations/
│           ├── __init__.py
│           ├── jsonl.py
│           └── claude_code.py
└── tests/
    ├── test_chunker.py
    ├── test_extractors.py
    ├── test_module.py
    └── fixtures/
        └── sample-module/
            ├── module.yaml
            └── content/
                └── overview.md
```

## pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ctx-modules"
version = "0.1.0"
description = "Context module system for RAG and AI coding tools"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "tiktoken>=0.5",
]

[project.optional-dependencies]
extractors = [
    "pymupdf>=1.23",
    "python-pptx>=0.6",
    "markdownify>=0.11",
]

[project.scripts]
ctx = "ctx.cli:cli"
```
