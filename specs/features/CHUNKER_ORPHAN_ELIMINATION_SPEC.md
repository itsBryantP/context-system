# Orphan Chunk Elimination — Specification

**Phase:** 2 of `plans/active/CHUNKING_IMPROVEMENTS_PLAN.md`

## Problem

`HeadingChunker` emits chunks whose content is **only a heading line** in two structural cases. On the `zconfig/docs` evaluation corpus, 15 of 147 chunks (10%) are such orphans — e.g. a 5-token chunk containing only `"# CICS Discovery Architecture"` with no body.

Orphan chunks score well on lexical/embedding similarity to the title alone (the title itself is the most on-topic string possible) but carry zero actionable content. They waste retrieval slots in any top-k scheme.

### Case A — file-level preamble is only an H1

```markdown
# CICS Discovery Architecture

## Component Overview
...
```

Current behavior: emits a preamble chunk with content `"# CICS Discovery Architecture"` (orphan). Then emits `## Component Overview` as a separate chunk (not orphan).

### Case B — H2 has only H3 subsections (no intermediate body)

```markdown
## Key Conventions

### Chunk IDs
...

### Tokenization
...
```

When `heading_level=2`, the current chunker takes the H2 section as a single unit, finds it too large, falls back to H3 splitting — at which point the parent H2's bare heading line becomes a tiny orphan if the H2 body between heading and first H3 is empty.

Actually observed in CLAUDE.md: `eval-real/claude/key-conventions` at 4 tokens, content = `"## Key Conventions"`.

## Behavior

### Invariant

```
For every Chunk c produced by HeadingChunker:
    not _is_orphan_heading(c.content)
```

### Definition — `_is_orphan_heading(text: str) -> bool`

Returns `True` if and only if, after `text.strip()`, every non-empty line matches the regex `^#{1,6}\s+\S.*$` (any markdown heading, levels 1–6). Blank lines are tolerated.

Examples:

| Content | `_is_orphan_heading` |
|---------|----------------------|
| `"# Title"` | True |
| `"# Title\n"` | True |
| `"## A\n\n### B"` | True |
| `"# Title\n\nParagraph."` | False (has non-heading content) |
| `"## Section\n\n- item"` | False |
| `"   "` | True (vacuously — no non-empty lines) |

### Case A handling (preamble elimination)

In `HeadingChunker._split_at_level`, when computing the pre-H2 preamble:

```python
preamble = content[: matches[0].start()].strip()
if preamble and not _is_orphan_heading(preamble):
    sections.append(([], preamble))
```

Silently drops orphan preambles. The H1 text is captured separately for Phase 3's `doc_title` metadata (see `CHUNKER_METADATA_SPEC.md`).

### Case B handling (empty H2 body elimination)

In `HeadingChunker.chunk`, when a section exceeds `max_tokens` and the implementation splits it at the next heading level:

```python
sub_sections = self._split_at_level(section_content, heading_level + 1)
if len(sub_sections) > 1:
    # Drop orphan parent heading before emitting sub-sections
    sub_sections = [
        (path, body) for path, body in sub_sections
        if not _is_orphan_heading(body)
    ]
    # emit filtered sub_sections as before
```

The H2 heading is still carried in each child's `section_path` via the existing `full_path = section_path + sub_path` logic — readers can still see the parent breadcrumb.

### What happens to small sections where the whole section IS a heading?

A section that fits within `max_tokens` but whose entire body is just a heading (rare — it means the doc has `## A\n\n## B` with no content anywhere) would currently be emitted as an orphan. The spec extends the invariant to all emission paths:

```python
if token_count <= max_tokens:
    if _is_orphan_heading(section_content):
        continue  # silently skip
    chunks.append(self._make_chunk(...))
```

## Examples

### Example 1 — simple preamble drop

**Input:**
```markdown
# API Patterns

## Authentication
Use JWT.

## Authorization
Use roles.
```

**Before:** 3 chunks (`eval/api/` orphan with `# API Patterns`, `authentication`, `authorization`).
**After:** 2 chunks (`authentication`, `authorization`). `doc_title="API Patterns"` lives in metadata.

### Example 2 — H2 with only H3 subsections

**Input:**
```markdown
## Key Conventions

### Chunk IDs
Deterministic.

### Tokenization
tiktoken.
```

**Before:** Three chunks — orphan `## Key Conventions`, `chunk-ids`, `tokenization`.
**After:** Two chunks — `chunk-ids` and `tokenization`, each with `section_path = ["Key Conventions", "Chunk IDs"]` and `["Key Conventions", "Tokenization"]`.

### Example 3 — legitimate preamble preserved

**Input:**
```markdown
# API Patterns

This module documents REST API design rules used across our services.

## Authentication
...
```

**Behavior:** Preamble chunk is emitted — it contains prose after the H1, which is not an orphan. Content stays as-is (H1 line included, since it's useful context for the preamble).

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Entire file is nothing but headings | Zero chunks emitted. Empty list is valid output. |
| Preamble is `# Title\n<!-- comment -->` | Comment counts as non-heading content → preamble kept. |
| H2 has a single blank-line-stripped sentence before first H3 | Not an orphan (sentence is non-heading content) → H2 section emitted as its own chunk. |
| Mid-section oversized split produces an orphan first piece | The token-window fallback from `FixedChunker` doesn't split on headings, so this can't happen from that path. The orphan check only runs in `HeadingChunker` emission paths. |

## Relation to `DefinitionChunker`

Not modified in this phase. Definition chunks are term-keyed (a definition is always a term plus its body), and empty-body definitions are rare in practice. Revisit only if a glossary-style corpus evaluation surfaces the same issue.

## Tests (behavior)

1. **Preamble-only-H1 dropped.** Input per Example 1 → 2 chunks, neither contains `"# API Patterns"` as its full content.
2. **Empty-H2 dropped.** Input per Example 2 → 2 chunks, no orphan parent.
3. **Legitimate preamble preserved.** Input per Example 3 → 3 chunks.
4. **Pure-heading file.** Input `"# A\n\n## B\n\n## C"` → 0 chunks.
5. **Helper unit tests.** `_is_orphan_heading` against the tabulated examples above.
6. **Real corpus regression.** `ctx pack zconfig/docs` produces `min(token_counts) >= 20` and `orphan_count == 0` where orphan means content matches `_is_orphan_heading`.

## Non-Goals

- Doesn't apply to `FixedChunker` or `DefinitionChunker` — neither routinely produces heading-only chunks in practice.
- Doesn't merge a dropped heading's content into an adjacent chunk. The heading text is preserved via `section_path` / `doc_title` metadata only.
- Doesn't change chunk IDs or ordering of non-orphan chunks.
