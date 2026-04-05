# ctx pack — Zero-Config Module Packaging

## Problem

The current `ctx` workflow is powerful but requires a user to understand module structure, write YAML manifests, run extraction commands per file, and manually configure chunking. For the most common case — "I have a folder of docs, I want chunks" — this is too many steps.

```bash
# Current: 6 steps, requires module system knowledge
ctx create api-docs
cp ~/docs/*.pdf ~/docs/*.md api-docs/content/   # wrong — PDFs must be extracted
ctx extract ~/docs/spec.pdf --into api-docs
ctx extract ~/docs/arch.pptx --into api-docs
# edit api-docs/module.yaml to set name, tags, chunking...
ctx build
```

## Solution

A single command that accepts any directory of mixed files and does the right thing.

```bash
# New: 1 step
ctx pack ~/docs/api-knowledge/

# That directory can contain anything:
# ~/docs/api-knowledge/
# ├── spec.pdf
# ├── architecture.pptx
# ├── runbook.md
# ├── glossary.md
# ├── meeting-notes.txt
# └── diagrams/             ← non-extractable files are skipped with a warning
#     └── flow.png
```

The `pack` command:
1. Scans the directory for all supported files
2. Extracts non-markdown files (PDF, PPTX) into markdown
3. Selects a chunking strategy per file based on content structure
4. Produces JSONL output immediately

No `module.yaml`. No `content/` subdirectory convention. No separate extract-then-build pipeline.

---

## Command Interface

```
ctx pack <directory> [OPTIONS]
```

### Output modes

| Flag | Behavior |
|------|----------|
| *(default)* | JSONL to stdout — pipe to any consumer |
| `-o, --output <path>` | Write a full module to `<path>` (module.yaml + content/ + chunks/) |
| `--install` | Pack and immediately `ctx add` to the current project |
| `-f text` | Human-readable chunk output instead of JSONL |

### Configuration overrides (all optional)

| Flag | Default | Purpose |
|------|---------|---------|
| `--name <name>` | directory name, kebab-cased | Module name |
| `--description <text>` | auto-generated from first heading | One-line description |
| `--tags <t1,t2,...>` | auto-detected from content | Comma-separated tag list |
| `--strategy <s>` | auto-detected per file | Force a single chunking strategy for all files |
| `--max-tokens <n>` | 500 | Maximum tokens per chunk |
| `--overlap <n>` | 50 | Overlap tokens between chunks |

### Examples

```bash
# Stream chunks to stdout (most common)
ctx pack ~/docs/api-knowledge/

# Pipe to an embedding script
ctx pack ~/docs/api-knowledge/ | python embed.py

# Inspect human-readable output
ctx pack ~/docs/api-knowledge/ -f text | less

# Write a proper module (can be versioned, shared, customized later)
ctx pack ~/docs/api-knowledge/ -o ./api-knowledge-module

# Pack and immediately install into the current project
ctx pack ~/docs/api-knowledge/ --install

# Override inferred settings
ctx pack ~/docs/api-knowledge/ --name api-v2 --tags api,rest --strategy heading
```

---

## Processing Pipeline

### Step 1: Scan

Recursively walk the input directory. Classify every file by extension:

| Extension | Classification | Action |
|-----------|---------------|--------|
| `.md`, `.markdown` | Markdown | Use directly (strip frontmatter) |
| `.txt` | Plain text | Treat as markdown |
| `.pdf` | PDF | Extract via pdftotext / PyMuPDF |
| `.pptx`, `.ppt` | PowerPoint | Extract via python-pptx |
| `.yaml`, `.yml`, `.json` | Structured data | Render as fenced code blocks in markdown |
| `.html`, `.htm` | HTML | Convert via markdownify |
| All others | Unsupported | Skip with a warning to stderr |

Files and directories whose names start with `.` or `_` are skipped silently (hidden files, `__pycache__`, etc.).

Output of this step: a list of `(source_path, classification)` pairs, sorted by path for deterministic output.

### Step 2: Extract

For each non-markdown file, run the appropriate extractor. All extraction happens in a temporary directory — the input directory is never modified.

Extracted markdown files carry their source filename as the document title:

```markdown
# spec                   ← derived from spec.pdf
## Authentication
...
```

For structured data files (YAML, JSON), wrap content in a code block with the original filename as heading:

```markdown
# config.yaml

\```yaml
database:
  host: localhost
  port: 5432
\```
```

If extraction fails for a file (corrupt PDF, missing optional dependency), log a warning to stderr and continue with the remaining files. Never abort the whole pack over a single broken file.

### Step 3: Analyze and select chunking strategy

For each markdown document (original or extracted), analyze its structure to select the best chunking strategy. The analysis is a simple heuristic, not ML:

```
function select_strategy(content: str) -> ChunkingStrategy:
    headings_h2 = count of ## headings
    headings_h3h4 = count of ### or #### headings
    bold_defs = count of **Term**: or **Term** — patterns
    paragraphs = count of double-newline-separated blocks
    total_tokens = token count of entire content

    if total_tokens <= max_tokens:
        return FIXED  # entire file fits in one chunk, strategy doesn't matter

    if bold_defs >= 3 and bold_defs > headings_h2:
        return DEFINITION

    if headings_h3h4 >= 3 and headings_h3h4 > headings_h2 * 2:
        return DEFINITION

    if headings_h2 >= 2:
        return HEADING

    return FIXED
```

This can be overridden with `--strategy` to force a single strategy across all files.

### Step 4: Chunk

Run each document through its selected chunker. Module-level metadata for the chunks:

| Field | Value |
|-------|-------|
| `module` | the `--name` value or auto-derived name |
| `version` | `"0.1.0"` (default for packs) |
| `tags` | from `--tags` or auto-detected |
| `source_file` | relative path of the original input file (not the temp extracted path) |

The `source_file` in chunk metadata always refers to the **original input path** within the directory, so a chunk from `spec.pdf` has `source_file: "spec.pdf"` not `source_file: "content/spec.md"`.

### Step 5: Output

Depends on the output mode chosen:

**stdout (default):** Emit JSONL lines to stdout. Warnings and progress go to stderr. This means `ctx pack dir/ 2>/dev/null` gives clean JSONL and `ctx pack dir/ > chunks.jsonl` captures output while progress remains visible.

**`-o <path>` (module output):** Write a complete, valid module directory:

```
<path>/
├── module.yaml              # auto-generated manifest
├── content/                 # extracted markdown files
│   ├── spec.md              # from spec.pdf
│   ├── architecture.md      # from architecture.pptx
│   ├── runbook.md           # copied directly
│   └── glossary.md          # copied directly
└── chunks/                  # pre-built JSONL
    └── <name>.jsonl
```

The generated `module.yaml` records the detected configuration so the user can inspect, version, and customize it:

```yaml
# Auto-generated by ctx pack — edit freely
name: api-knowledge
version: 0.1.0
description: "API specification, architecture overview, and operational runbook"
tags:
  - api
  - architecture
chunking:
  strategy: heading           # majority strategy; per-file overrides below
  max_tokens: 500
  overlap_tokens: 50
  heading_level: 2
  overrides:
    - pattern: "content/glossary.md"
      strategy: definition
sources:                      # original input files (for ctx sync)
  - type: pdf
    path: ~/docs/api-knowledge/spec.pdf
  - type: pptx
    path: ~/docs/api-knowledge/architecture.pptx
  - type: markdown
    path: ~/docs/api-knowledge/runbook.md
  - type: markdown
    path: ~/docs/api-knowledge/glossary.md
```

This module is now a standard `ctx` module. The user can run `ctx add`, `ctx build`, `ctx sync`, edit the YAML, add skills/rules — the full power of the module system is available as an off-ramp from the zero-config path.

**`--install`:** Equivalent to `-o <tmpdir>` followed by `ctx add <tmpdir>`. The module is materialized in `.context/packed/<name>/` within the project so it persists and can be rebuilt.

---

## Auto-Detection Details

### Module name

Derived from the input directory name. Apply kebab-case normalization:

```
~/Documents/API Knowledge Base  →  api-knowledge-base
./My Docs                       →  my-docs
/tmp/v2_api_specs               →  v2-api-specs
```

Override with `--name`.

### Description

Use the first H1 heading found across all input files. If no H1 exists, use `"Context module packed from <directory-name>"`.

### Tags

Scan all extracted markdown content for recurring domain terms. Use a simple frequency-based approach over headings and bold terms:

1. Collect all H1–H3 heading texts and bold terms
2. Tokenize into lowercase words, drop stop words and words under 3 characters
3. Count frequency across all documents
4. Take the top 3–5 terms that appear in at least 2 documents

This is intentionally shallow. Tags are metadata hints, not a classification system. The user can always override with `--tags`.

If fewer than 2 terms meet the threshold, fall back to no auto-tags (empty list).

---

## Interaction with Existing Commands

`ctx pack` is an on-ramp, not a replacement. The relationship:

```
  ctx pack (zero-config)
       │
       │  -o flag produces a standard module
       ▼
  ctx create / ctx extract / module.yaml editing (full control)
       │
       ▼
  ctx build / ctx add / ctx chunks (consumption)
```

A user who starts with `ctx pack` and later needs more control (per-file chunking overrides, skills, rules, dependencies) can use `-o` to emit a module and then work with it using the standard commands.

`ctx pack` never modifies the input directory. It reads files, processes them in a temp directory, and writes output to stdout or a specified path.

---

## Progress and Feedback

All progress output goes to stderr so stdout stays clean for JSONL piping.

```
$ ctx pack ~/docs/api-knowledge/ > chunks.jsonl
Scanning ~/docs/api-knowledge/...
  Found 4 supported files, skipping 1 unsupported (diagrams/flow.png)

Extracting:
  spec.pdf → markdown (pdftotext)
  architecture.pptx → markdown (python-pptx)
  runbook.md → ready
  glossary.md → ready

Chunking:
  spec.md: heading strategy → 23 chunks
  architecture.md: heading strategy → 12 chunks
  runbook.md: fixed strategy → 8 chunks
  glossary.md: definition strategy → 15 chunks

Packed api-knowledge: 58 chunks, 4 files
```

When using `--install`:

```
$ ctx pack ~/docs/api-knowledge/ --install
Scanning ~/docs/api-knowledge/...
  Found 4 supported files

Extracting...
Chunking...

Module written to .context/packed/api-knowledge/
  skill      → (none)
  rule       → (none)
  CLAUDE.md  → (none)
  api-knowledge: 58 chunks → .context/chunks/api-knowledge.jsonl

Installed api-knowledge into project
```

---

## Error Handling

| Situation | Behavior |
|-----------|----------|
| Empty directory | Error: "No supported files found in `<dir>`" |
| All extractions fail | Error: "Could not extract any files. Check dependencies (poppler, python-pptx, markdownify)." |
| Some extractions fail | Warning per file on stderr; continue with successful ones |
| Input directory doesn't exist | Error: standard Click path validation |
| `-o` target already exists | Error: "Output directory `<path>` already exists. Remove it or choose a different path." |
| No extractors available for a file type | Warning: "`<file>`: no extractor for `.<ext>`, skipped" |
| File is empty or unreadable | Warning: "`<file>`: empty or unreadable, skipped" |

---

## Implementation Scope

### New files

| File | What |
|------|------|
| `src/ctx/pack.py` | Core pack logic: scan, extract, analyze, chunk, output |
| `tests/test_pack.py` | Unit tests for scan, strategy selection, end-to-end pack |

### Modified files

| File | What |
|------|------|
| `src/ctx/cli.py` | Add `pack` command |
| `src/ctx/schema.py` | No changes needed — pack produces standard `ModuleConfig` |

### No new dependencies

Everything needed is already available:
- File scanning: `pathlib.Path.rglob`
- Extraction: existing `ctx.extractors` registry
- Chunking: existing chunker implementations
- JSONL: existing `ctx.integrations.jsonl`
- YAML output: existing `pyyaml`
- Temp directories: `tempfile.TemporaryDirectory`

---

## Design Principles

1. **The input directory is sacred.** `ctx pack` never writes to, modifies, or rearranges the input. All work happens in temp space.

2. **Stdout is for data, stderr is for humans.** JSONL on stdout, progress on stderr. `ctx pack dir/ | jq` always works.

3. **Defaults should be right 80% of the time.** Strategy auto-detection, name inference, tag extraction — all designed so the common case needs zero flags.

4. **The off-ramp is a module.** `-o` produces a standard module that works with every existing `ctx` command. Pack is an entry point, not a silo.

5. **Fail gracefully, not loudly.** A corrupt PDF in a directory of 20 files should produce 19 files of chunks plus one warning, not a stack trace.
