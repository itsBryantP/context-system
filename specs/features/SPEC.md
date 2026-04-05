# ctx — Specification

## Overview

`ctx` is a Python CLI tool for creating, managing, and consuming **context modules** — portable units of knowledge designed for two consumption paths:

1. **RAG pipelines** — well-chunked JSONL with structured metadata, ingestible by any vector store
2. **AI coding tools** — native integration with Claude Code (skills, rules, CLAUDE.md), extensible to Cursor, Copilot, etc.

Modules are **native packages**, not abstracted data that needs adapters. A module directory maps directly to the integration points of the target tool.

---

## Module Structure

```
my-module/
├── module.yaml              # Required: metadata, chunking config, sources
├── content/                 # Required: markdown content files
│   ├── overview.md
│   ├── api-endpoints.md
│   └── glossary.md
├── CLAUDE.md                # Optional: Claude Code context (@importable)
├── skills/                  # Optional: Claude Code SKILL.md files
│   └── review-api/
│       └── SKILL.md
└── rules/                   # Optional: Claude Code path-scoped rules
    └── api-validation.md
```

### module.yaml Schema

```yaml
# Required fields
name: string                 # Module identifier (kebab-case)
version: string              # SemVer (e.g., "1.0.0")
description: string          # One-line description

# Optional fields
tags: [string]               # For chunk metadata and discovery
depends_on:                  # Other modules this depends on
  - module-name@version-range

# Source declarations (for ctx extract / ctx sync)
sources:
  - type: markdown | pdf | pptx | url
    path: string             # Glob pattern for local files
    url: string              # For url type
    refresh: daily | weekly | monthly  # For url type

# Chunking configuration
chunking:
  strategy: heading | fixed | definition
  max_tokens: 500            # Maximum tokens per chunk
  overlap_tokens: 50         # Overlap between consecutive chunks
  heading_level: 2           # For heading strategy: split at this level
  overrides:                 # Per-file chunking overrides
    - pattern: string        # Glob pattern matching content files
      strategy: heading | fixed | definition
      max_tokens: number
      overlap_tokens: number
      heading_level: number
```

### Field Details

**name**: Must be unique within a project's installed modules. Used as the JSONL filename and chunk ID prefix.

**version**: Follows SemVer. Included in chunk metadata for tracking which version of knowledge was embedded.

**tags**: Inherited by all chunks from this module. Individual content files can add additional tags via markdown frontmatter.

**sources**: Declares where content originates. Used by `ctx extract` and `ctx sync` to populate `content/`. Sources are extracted into markdown files under `content/`.

**chunking**: Controls how content files are split into chunks. The `overrides` array allows different strategies for different files within the same module (e.g., heading-based for docs, definition-based for glossaries).

---

## Project Configuration

### .context/config.yaml

Created by `ctx init` in the consuming project:

```yaml
# Installed modules
modules:
  - path: ~/context-modules/api-patterns
  - path: ./docs/local-context

# Default chunking (modules can override)
chunk_defaults:
  max_tokens: 500
  overlap_tokens: 50
  strategy: heading

# Output configuration
output:
  chunks_dir: .context/chunks    # Where JSONL files go
  claude_md: true                # Auto-manage CLAUDE.md imports
```

### .context/ Directory

```
.context/
├── config.yaml              # Project configuration
└── chunks/                  # Generated JSONL output (gitignored)
    ├── api-patterns.jsonl
    └── org-glossary.jsonl
```

---

## RAG Output Format

### JSONL Schema

Each line in a `.jsonl` file is a self-contained chunk:

```json
{
  "id": "api-patterns/api-endpoints/get-users",
  "module": "api-patterns",
  "source_file": "content/api-endpoints.md",
  "section_path": ["API Endpoints", "Users", "GET /users"],
  "content": "## GET /users\n\nReturns paginated list of users...",
  "metadata": {
    "tags": ["api", "architecture", "rest"],
    "version": "1.0.0",
    "chunk_index": 3,
    "total_chunks": 12,
    "token_count": 487,
    "heading_level": 3,
    "parent_section": "Users"
  }
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Deterministic, hierarchical: `{module}/{file-stem}/{section-slug}` |
| `module` | string | Source module name |
| `source_file` | string | Relative path within module |
| `section_path` | string[] | Full heading breadcrumb from H1 down |
| `content` | string | Raw markdown content of the chunk |
| `metadata.tags` | string[] | Module tags + any per-file tags |
| `metadata.version` | string | Module version at build time |
| `metadata.chunk_index` | number | Position within the source file's chunks |
| `metadata.total_chunks` | number | Total chunks from this source file |
| `metadata.token_count` | number | Pre-computed token count (tiktoken cl100k_base) |
| `metadata.heading_level` | number | Heading level this chunk was split at |
| `metadata.parent_section` | string | Immediate parent heading text |

### Design Decisions

- **Deterministic IDs**: Same content always produces the same chunk ID. Enables incremental RAG updates — only re-embed chunks whose content changed.
- **Section path**: Full breadcrumb allows reconstructing context hierarchy during retrieval. A retrieved chunk about "GET /users" carries its path `["API Endpoints", "Users", "GET /users"]` so the LLM knows where it sits.
- **Pre-computed token count**: Enables embedding budget management without re-tokenizing.
- **Raw markdown preserved**: Chunks keep their formatting. The consumer decides whether to strip it before embedding.

---

## Chunking Strategies

### Heading Strategy (default)

Splits markdown at heading boundaries, preserving document structure.

**Algorithm**:
1. Parse markdown into a heading tree (H1 → H2 → H3 → ...)
2. Split at `heading_level` boundaries (default: H2)
3. Each chunk includes its heading and all content until the next heading at the same or higher level
4. If a chunk exceeds `max_tokens`, recursively split at the next heading level
5. If still too large (no sub-headings), fall back to fixed-size splitting within that section
6. Each chunk's `section_path` is its full heading breadcrumb

**Best for**: Documentation, architecture docs, API references, guides.

### Fixed Strategy

Sliding window with paragraph-aware boundaries.

**Algorithm**:
1. Split content into paragraphs (double newline boundaries)
2. Accumulate paragraphs until reaching `max_tokens`
3. Emit chunk, then start next chunk with `overlap_tokens` of trailing content from previous chunk
4. Never splits mid-paragraph

**Best for**: Long-form prose without clear heading structure, transcripts, meeting notes.

### Definition Strategy

One chunk per definition, term, or entry.

**Algorithm**:
1. Identify definition blocks (pattern: bold/heading term followed by description)
2. Each definition = one chunk
3. If a definition exceeds `max_tokens`, use fixed strategy within it
4. Group small definitions together up to `max_tokens` to avoid micro-chunks

**Best for**: Glossaries, FAQs, changelogs, configuration references.

---

## Extractor Plugins

Extractors convert source formats into markdown content files.

### PDF Extractor
- Primary: `pdftotext` (poppler)
- Fallback: PyMuPDF
- OCR fallback: tesseract (for image-based PDFs)
- Output: markdown with heading detection from font sizes

### PowerPoint Extractor
- Primary: LibreOffice headless
- Fallback: python-pptx
- Output: markdown with `## Slide N` headings, speaker notes as blockquotes

### Markdown Extractor
- Passthrough with frontmatter parsing
- Extracts tags from frontmatter into chunk metadata
- Resolves relative links

### URL Extractor
- Fetches HTML, converts to markdown via `markdownify`
- Stores fetch timestamp for freshness tracking
- Respects `refresh` schedule in source config

### Extractor Interface

```python
class Extractor(ABC):
    @abstractmethod
    def can_handle(self, source: Source) -> bool: ...

    @abstractmethod
    def extract(self, source: Source, output_dir: Path) -> list[Path]:
        """Extract source into markdown files. Returns paths of created files."""
        ...
```

---

## Claude Code Integration

### Installation (`ctx add`)

When installing a module into a project:

1. **Skills**: Symlink each `skills/<name>/` directory to `.claude/skills/<name>`
2. **Rules**: Symlink each `rules/<name>.md` to `.claude/rules/<name>.md`
3. **CLAUDE.md**: Append `@<module-path>/CLAUDE.md` to the project's CLAUDE.md
4. **Config**: Record the module in `.context/config.yaml`

### Removal (`ctx remove`)

Reverses all of the above:
1. Remove skill symlinks
2. Remove rule symlinks
3. Remove the `@import` line from CLAUDE.md
4. Remove from `.context/config.yaml`

### Skills Accessing RAG Chunks

Skills can query their module's JSONL chunks at invocation time using shell injection:

```markdown
---
name: find-api-pattern
description: Search API patterns knowledge base
allowed-tools: Read, Grep, Bash
---
Search the chunked knowledge base for relevant patterns:
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

### Path-Scoped Rules

Rules use frontmatter to scope when they activate:

```markdown
---
paths:
  - "src/api/**/*.ts"
  - "src/routes/**/*.ts"
---

# API Validation Rules
- All endpoints must validate request bodies with zod schemas
- Return standard error format: { error: string, code: number, details?: object }
```

---

## Module Resolution

### MVP: Local Paths

```yaml
modules:
  - path: ~/context-modules/api-patterns    # Absolute
  - path: ./docs/local-context              # Relative to project root
```

### Future: Git URLs

```yaml
modules:
  - git: https://github.com/org/context-modules.git#api-patterns@v1.0
```

### Future: Registry

```yaml
modules:
  - registry: org/api-patterns@^1.0
```

Resolution order: local path → git URL → registry.

---

## Cross-Framework Support

Modules can carry parallel format files for multiple tools:

```
my-module/
├── module.yaml
├── content/
├── CLAUDE.md                # Claude Code
├── skills/                  # Claude Code
├── rules/                   # Claude Code
├── BOB.md                   # Bob Shell
├── bob/                     # Bob Shell
│   ├── modes/               # Custom modes
│   ├── tools/               # Custom tools
│   └── servers/             # MCP servers
├── .cursorrules             # Cursor
├── COPILOT.md               # GitHub Copilot
└── .continuerules           # Continue.dev
```

`ctx add` installs the appropriate files based on detected tooling in the project, or explicit `--tool` flag.

### Bob Shell Integration

Bob Shell uses:
- **BOB.md** — Context file (like CLAUDE.md)
- **Modes** — Specialized interaction contexts (`.bob/modes/*.yaml`)
- **Tools** — Custom capabilities (`.bob/tools/*.yaml`)
- **MCP Servers** — Model Context Protocol servers (`.bob/servers/*.json`)

Detection: `.bob/` directory or `BOB.md` file exists in project root.

See `specs/BOB_SPEC.md` for complete Bob Shell integration specification.
