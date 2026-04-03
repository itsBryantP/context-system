# ctx — Context Module System

A Python CLI for packaging knowledge into **portable context modules** — structured units that feed both RAG pipelines and AI coding tools from the same source of truth.

```
ctx create api-patterns          # scaffold a module
ctx extract spec.pdf --into ./api-patterns   # ingest a PDF
ctx build                        # produce JSONL chunks
ctx add ./api-patterns           # wire into Claude Code
```

---

## Why

AI coding assistants need project-specific context: API contracts, architecture decisions, internal glossaries, runbooks. That knowledge lives in PDFs, slide decks, wikis, and Confluence pages — not in the LLM's weights.

Most teams solve this by copy-pasting into system prompts, which doesn't scale, or by building one-off pipelines that don't compose.

`ctx` defines a **module** — a directory that carries content, chunking configuration, and AI-tool integration files together. The same module produces RAG-ready JSONL *and* Claude Code skills/rules/CLAUDE.md imports. You author it once and consume it everywhere.

---

## Installation

```bash
pip install ctx-modules

# With optional extractors (PDF, PPTX, URL → markdown):
pip install "ctx-modules[extractors]"
```

**Requirements:** Python 3.11+, `git` on PATH (for git URL modules)

For PDF extraction, also install poppler:
```bash
brew install poppler          # macOS
apt-get install poppler-utils # Linux
```

---

## Core Concepts

**Module** — a directory with a `module.yaml` manifest, a `content/` folder of markdown files, and optional AI-tool integration files (skills, rules, CLAUDE.md).

**Chunk** — a semantically meaningful slice of content with a deterministic ID, token count, and metadata. The atom of RAG retrieval.

**Two consumption paths:**
1. `ctx build` → `.context/chunks/*.jsonl` — pipe to any vector store
2. `ctx add` → `.claude/skills/`, `.claude/rules/`, CLAUDE.md imports — native Claude Code integration

---

## Quick Start

```bash
# 1. Create a module
ctx create api-patterns
cd api-patterns

# 2. Add content (or extract it — see Extraction below)
# Edit content/overview.md with your knowledge

# 3. Initialize a project and build
cd ~/my-project
ctx init
ctx add ~/api-patterns

# 4. Build RAG chunks
ctx build

# 5. Stream chunks to stdout (pipe anywhere)
ctx chunks ~/api-patterns | head -5
```

---

## End-to-End Walkthrough

This walkthrough builds a real module from scratch: an **API patterns** knowledge base extracted from existing docs, chunked for RAG, and wired into an active project.

### 1. Create the module scaffold

```bash
ctx create api-patterns
```

This produces:

```
api-patterns/
├── module.yaml
└── content/
    └── overview.md
```

### 2. Configure the module

Edit `api-patterns/module.yaml`:

```yaml
name: api-patterns
version: 1.0.0
description: REST API design patterns and conventions for the platform

tags:
  - api
  - architecture
  - rest

chunking:
  strategy: heading
  max_tokens: 400
  overlap_tokens: 50
  heading_level: 2

sources:
  - type: pdf
    path: ~/docs/api-spec.pdf
  - type: url
    url: https://internal-wiki.example.com/api-conventions
    refresh: weekly
  - type: markdown
    path: ~/docs/architecture/*.md
```

### 3. Extract content from existing sources

Pull in the PDF spec:

```bash
ctx extract ~/docs/api-spec.pdf --into ./api-patterns
# Extracted → content/api-spec.md
```

Fetch the internal wiki page:

```bash
ctx extract https://internal-wiki.example.com/api-conventions --into ./api-patterns
# Extracted → content/api-conventions.md
```

Copy and process local markdown docs:

```bash
ctx extract ~/docs/architecture/patterns.md --into ./api-patterns
# Extracted → content/patterns.md
```

Or re-run all sources declared in `module.yaml` at once:

```bash
ctx sync ./api-patterns
# [pdf]      → api-spec.md
# [url]      → api-conventions.md
# [markdown] → patterns.md
# Synced 3 file(s) for api-patterns
```

### 4. Validate the module

```bash
ctx validate ./api-patterns
#   ✓ api-patterns v1.0.0 is valid
```

### 5. Build JSONL chunks

```bash
cd ~/my-project
ctx init          # creates .context/config.yaml
ctx add ~/api-patterns
ctx build
#   api-patterns: 47 chunks → .context/chunks/api-patterns.jsonl
#   Build complete: 47 total chunks
```

Subsequent builds skip unchanged modules:

```bash
ctx build
#   api-patterns: up to date (skipped)
#   Build complete: 0 total chunks
```

Force a full rebuild:

```bash
ctx build --force
#   api-patterns: 47 chunks → .context/chunks/api-patterns.jsonl
```

### 6. Inspect the output

Stream to stdout and pipe anywhere:

```bash
# Pipe to an embedding script
ctx chunks ~/api-patterns | python embed.py

# Inspect as readable text
ctx chunks ~/api-patterns -f text | head -40

# Pretty-print a single chunk
ctx chunks ~/api-patterns | python3 -m json.tool --json-lines | head -30
```

Each line is a self-contained JSON object:

```json
{
  "id": "api-patterns/api-spec/authentication",
  "module": "api-patterns",
  "source_file": "content/api-spec.md",
  "section_path": ["Authentication"],
  "content": "## Authentication\n\nAll API requests must include...",
  "metadata": {
    "tags": ["api", "architecture", "rest"],
    "version": "1.0.0",
    "chunk_index": 3,
    "total_chunks": 47,
    "token_count": 312,
    "heading_level": 1,
    "parent_section": null,
    "source_hash": "a3f8c2..."
  }
}
```

### 7. Use with Claude Code

```bash
ctx add ~/api-patterns --project ~/my-project
#   skill      → .claude/skills/review-api
#   rule       → .claude/rules/api-validation.md
#   CLAUDE.md  → @import added
#   Added api-patterns
```

Claude Code now has:
- Skills available at `.claude/skills/review-api/SKILL.md`
- Path-scoped rules active for `src/api/**`
- The module's CLAUDE.md imported at the bottom of your project's CLAUDE.md

Remove when done:

```bash
ctx remove api-patterns
#   removed skill      .claude/skills/review-api
#   removed rule       .claude/rules/api-validation.md
#   removed CLAUDE.md  @import
#   Removed api-patterns
```

---

## Module Structure

```
api-patterns/
├── module.yaml              # Required: manifest, chunking config, sources
├── content/                 # Required: markdown content (authored or extracted)
│   ├── overview.md
│   ├── api-spec.md
│   └── authentication.md
├── CLAUDE.md                # Optional: imported into consuming project's CLAUDE.md
├── skills/                  # Optional: Claude Code skill directories
│   └── review-api/
│       └── SKILL.md
├── rules/                   # Optional: path-scoped Claude Code rules
│   └── api-validation.md
├── .cursorrules             # Optional: Cursor rules
├── COPILOT.md               # Optional: GitHub Copilot instructions
└── .continuerules           # Optional: Continue.dev rules
```

### module.yaml Reference

```yaml
# Required
name: api-patterns           # kebab-case identifier, unique within a project
version: 1.0.0               # SemVer
description: "..."           # one-line description

# Optional
tags:                        # inherited by all chunks from this module
  - api
  - architecture

depends_on:                  # other modules this one builds on
  - org-glossary@^1.0
  - auth-patterns

# Source declarations (for ctx extract / ctx sync)
sources:
  - type: pdf
    path: ~/docs/spec.pdf
  - type: pptx
    path: ~/docs/presentation.pptx
  - type: url
    url: https://wiki.example.com/page
    refresh: weekly           # daily | weekly | monthly
  - type: markdown
    path: docs/**/*.md        # glob patterns supported

# Chunking configuration
chunking:
  strategy: heading           # heading | fixed | definition
  max_tokens: 500
  overlap_tokens: 50
  heading_level: 2            # split at H2 (heading strategy only)
  overrides:                  # per-file strategy overrides
    - pattern: "content/glossary.md"
      strategy: definition
      max_tokens: 300
```

---

## Chunking Strategies

### `heading` (default)

Splits at heading boundaries. Preserves document structure. Best for API docs, architecture docs, guides.

```
## Authentication              → chunk 1
All API requests must...

## Pagination                  → chunk 2
Use cursor-based pagination...
```

If a section exceeds `max_tokens`, it recursively tries the next heading level, then falls back to fixed splitting.

### `fixed`

Sliding window over paragraphs. Never splits mid-paragraph. Best for long prose, transcripts, meeting notes.

```yaml
chunking:
  strategy: fixed
  max_tokens: 400
  overlap_tokens: 75
```

### `definition`

One chunk per term/entry. Detects H3/H4 headings or `**Bold**: description` patterns. Groups small definitions together up to `max_tokens`. Best for glossaries, FAQs, changelogs, config references.

```markdown
### GET /users
Returns a paginated list of users...

### POST /users
Creates a new user. Requires...
```

```markdown
**idempotency-key**: A client-generated UUID included in POST requests...
**cursor**: An opaque string returned in paginated responses...
```

### Per-file overrides

Apply a different strategy to specific files:

```yaml
chunking:
  strategy: heading
  max_tokens: 500
  overrides:
    - pattern: "content/glossary.md"
      strategy: definition
      max_tokens: 300
    - pattern: "content/changelog.md"
      strategy: definition
```

---

## Source Extraction

`ctx extract` and `ctx sync` populate `content/` from raw source files.

### PDF

```bash
ctx extract ~/docs/spec.pdf --into ./my-module
# Uses pdftotext (poppler) if available, falls back to PyMuPDF
# Detects headings from font sizes
# Output: content/spec.md
```

### PowerPoint

```bash
ctx extract ~/docs/deck.pptx --into ./my-module
# Each slide → ## Slide N heading
# Speaker notes → > blockquotes
# Output: content/deck.md
```

### URL

```bash
ctx extract https://docs.example.com/api --into ./my-module
# Fetches HTML, converts via markdownify
# Stores source_url and fetched_at in frontmatter
# Output: content/api.md
```

### Markdown

```bash
ctx extract ~/docs/guide.md --into ./my-module
# Strips YAML frontmatter, copies body
# Glob patterns supported for bulk import
ctx extract "~/docs/runbooks/*.md" --into ./my-module
```

### Sync all declared sources

```bash
# Run all sources in module.yaml at once
ctx sync ./my-module
```

---

## Claude Code Integration

When you run `ctx add`, the module is wired into the project:

| Module file | Installed as |
|-------------|-------------|
| `skills/<name>/` | Symlink at `.claude/skills/<name>` |
| `rules/<name>.md` | Symlink at `.claude/rules/<name>.md` |
| `CLAUDE.md` | `@<abs-path>/CLAUDE.md` appended to project CLAUDE.md |

Skills can query the module's JSONL chunks at invocation time:

```markdown
---
name: find-api-pattern
description: Search API patterns knowledge base
allowed-tools: Bash
---
Search for relevant patterns in the chunked knowledge base:
!`cat .context/chunks/api-patterns.jsonl | python3 -c "
import sys, json
query = '$ARGUMENTS'.lower()
for line in sys.stdin:
    chunk = json.loads(line)
    if query in chunk['content'].lower():
        print(chunk['content'][:500])
        print('---')
"`
```

Rules use frontmatter to scope when they activate:

```markdown
---
paths:
  - "src/api/**/*.ts"
  - "src/routes/**/*.ts"
---

# API Validation Rules
- All endpoints must validate request bodies
- Return standard error format: { error: string, code: number }
```

---

## Cross-Framework Support

A module can carry rule files for multiple AI tools:

```
my-module/
├── CLAUDE.md          # Claude Code
├── skills/            # Claude Code
├── rules/             # Claude Code
├── .cursorrules       # Cursor
├── COPILOT.md         # GitHub Copilot
└── .continuerules     # Continue.dev
```

`ctx add` auto-detects which tools are active in the project:

```bash
# Auto-detect: installs Claude files + any detected tool files
ctx add ~/api-patterns

# Explicit: install for specific tools
ctx add ~/api-patterns --tool claude --tool cursor

# All tools at once
ctx add ~/api-patterns --tool claude --tool cursor --tool copilot --tool continue
```

Detection heuristics:
- **cursor** — `.cursor/` directory or `.cursorrules` file exists
- **copilot** — `.github/` directory exists
- **continue** — `.continuerules` file exists

---

## Git URL Modules

Modules can be referenced from git repositories without a local clone:

```yaml
# .context/config.yaml
modules:
  - path: ~/shared-modules/api-patterns    # local path
  - git: https://github.com/org/context-modules.git#api-patterns@v1.0
  - git: https://github.com/org/context-modules.git#org-glossary@main
```

Git URL format: `https://...repo.git[#subdir][@ref]`

- `#subdir` — path to the module within the repo (optional; root if omitted)
- `@ref` — branch, tag, or commit (optional; defaults to HEAD)

Repos are cloned once to `~/.ctx/cache/` and reused across projects. Delete the cache to force a re-clone:

```bash
rm -rf ~/.ctx/cache/
ctx build --force
```

---

## Module Dependencies

Declare that one module builds on another:

```yaml
# org-api-patterns/module.yaml
name: org-api-patterns
depends_on:
  - org-glossary@^1.0
  - auth-patterns
```

`ctx build` warns if declared dependencies are not installed in the project:

```
Warning: org-api-patterns depends on 'org-glossary' which is not installed
```

To install all related modules:

```bash
ctx add ~/org-glossary
ctx add ~/auth-patterns
ctx add ~/org-api-patterns
ctx build
```

---

## CLI Reference

### `ctx init [path]`

Initialize `.context/config.yaml` in the project root.

```bash
ctx init                  # current directory
ctx init ~/my-project     # explicit path
```

### `ctx create <name>`

Scaffold a new module directory.

```bash
ctx create api-patterns
ctx create --path ~/modules api-patterns   # create in specific parent dir
```

### `ctx extract <source> --into <module>`

Extract a source file or URL into a module's `content/` directory.

```bash
ctx extract spec.pdf --into ./api-patterns
ctx extract deck.pptx --into ./api-patterns
ctx extract https://docs.example.com --into ./api-patterns
ctx extract guide.md --into ./api-patterns
ctx extract "docs/**/*.md" --into ./api-patterns    # glob

# Force a specific type
ctx extract notes.txt --into ./api-patterns --type markdown
```

### `ctx sync <module>`

Re-extract all `sources:` declared in `module.yaml`.

```bash
ctx sync ./api-patterns
```

### `ctx validate <module>`

Check module structure and schema validity.

```bash
ctx validate ./api-patterns
#   ✓ api-patterns v1.0.0 is valid
```

### `ctx build`

Build JSONL chunks for all modules in `.context/config.yaml`. Skips unchanged modules by default.

```bash
ctx build                   # incremental (skips fresh modules)
ctx build --force           # always rebuild
ctx build --project ~/app   # explicit project root
```

### `ctx chunks <module>`

Stream a module's chunks to stdout without writing to disk.

```bash
ctx chunks ./api-patterns                    # JSONL (default)
ctx chunks ./api-patterns -f text            # human-readable
ctx chunks ./api-patterns | wc -l            # count chunks
ctx chunks ./api-patterns | python embed.py  # pipe to embedding script
```

### `ctx list`

List modules configured in the project.

```bash
ctx list
#   api-patterns v1.0.0 — REST API design patterns (3 files)  [/home/user/api-patterns]
#   org-glossary v2.1.0 — Organisation-wide glossary (1 file)  [github.com/org/modules#glossary]
```

### `ctx add <module>`

Install a module's skills, rules, CLAUDE.md, and cross-framework files into the project.

```bash
ctx add ~/api-patterns                              # auto-detect tools
ctx add ~/api-patterns --tool claude                # Claude Code only
ctx add ~/api-patterns --tool claude --tool cursor  # Claude + Cursor
ctx add ~/api-patterns --project ~/my-project       # explicit project
```

### `ctx remove <name>`

Remove a module from the project, cleaning up all installed files.

```bash
ctx remove api-patterns
ctx remove api-patterns --project ~/my-project
```

---

## RAG Integration

The JSONL output is designed for minimal friction with any vector store.

### Pipe to an embedding script

```bash
ctx chunks ./api-patterns | python3 << 'EOF'
import sys, json
import openai

client = openai.OpenAI()
for line in sys.stdin:
    chunk = json.loads(line)
    embedding = client.embeddings.create(
        input=chunk["content"],
        model="text-embedding-3-small"
    ).data[0].embedding
    print(json.dumps({"id": chunk["id"], "embedding": embedding, **chunk}))
EOF
```

### Incremental updates

Chunk IDs are deterministic (`{module}/{file-stem}/{section-slug}`). If content hasn't changed, the ID and content are identical to the previous build — you can use the ID to detect which chunks need re-embedding:

```bash
# Only embed chunks that don't already exist in your vector store
ctx chunks ./api-patterns | python3 upsert_changed.py
```

### JSONL schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `{module}/{file-stem}/{section-slug}` — deterministic |
| `module` | string | Module name |
| `source_file` | string | Relative path within module |
| `section_path` | string[] | Full heading breadcrumb |
| `content` | string | Raw markdown content of the chunk |
| `metadata.tags` | string[] | Module tags |
| `metadata.version` | string | Module version at build time |
| `metadata.chunk_index` | number | Position within source file's chunks |
| `metadata.total_chunks` | number | Total chunks from this file |
| `metadata.token_count` | number | Pre-computed token count (cl100k_base) |
| `metadata.source_hash` | string | SHA-256 of module content at build time |

---

## Project Configuration

### `.context/config.yaml`

Created by `ctx init`. Stores installed modules and build defaults.

```yaml
modules:
  - path: /home/user/api-patterns
  - path: ./docs/local-context
  - git: https://github.com/org/modules.git#shared/glossary@v2.0

chunk_defaults:
  max_tokens: 500
  overlap_tokens: 50
  strategy: heading

output:
  chunks_dir: .context/chunks
  claude_md: true
```

### `.context/` directory layout

```
.context/
├── config.yaml              # project configuration (commit this)
├── .build-meta.json         # freshness tracking — source hashes (commit optional)
└── chunks/                  # generated JSONL output (gitignore this)
    ├── api-patterns.jsonl
    └── org-glossary.jsonl
```

Add to `.gitignore`:

```
.context/chunks/
```

---

## Development

### Setup

```bash
git clone https://github.com/itsBryantP/context-system.git
cd context-system
uv sync
uv pip install -e ".[dev,extractors]"
```

### Tests

```bash
uv run pytest                    # all tests (115)
uv run pytest tests/test_chunker.py -v
uv run pytest -k "definition"    # filter by name
```

### Project structure

```
src/ctx/
├── cli.py             # Click entry points
├── schema.py          # Pydantic models (ModuleConfig, ProjectConfig, ModuleRef)
├── config.py          # .context/config.yaml load/save
├── module.py          # load_module, validate_module, resolve_module_ref
├── deps.py            # dependency resolution
├── freshness.py       # build metadata and hash-based skip logic
├── git.py             # git clone/cache for git: module refs
├── chunker/
│   ├── base.py        # ChunkStrategy ABC, Chunk dataclass, tokenizer
│   ├── heading.py     # heading-boundary splitting
│   ├── fixed.py       # paragraph-aware sliding window
│   └── definition.py  # term/entry detection and grouping
├── extractors/
│   ├── base.py        # Extractor ABC
│   ├── markdown.py    # frontmatter-stripping passthrough
│   ├── pdf.py         # pdftotext + PyMuPDF fallback
│   ├── pptx.py        # python-pptx slide extraction
│   └── url.py         # urllib + markdownify
└── integrations/
    ├── jsonl.py       # JSONL serialization
    └── claude_code.py # symlink management, CLAUDE.md patching, cross-tool files
```

---

## License

MIT
