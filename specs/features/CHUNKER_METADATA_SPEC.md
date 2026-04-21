# Chunk Metadata Additions — Specification

**Phase:** 3 of `plans/active/CHUNKING_IMPROVEMENTS_PLAN.md`

## Problem

Chunks currently carry metadata sufficient for display (`heading_level`, `parent_section`, `token_count`, `chunk_index`, `total_chunks`) but not for retrieval consumers that want to:

- Distinguish code-heavy chunks from prose (mode-aware retrieval)
- Expand a retrieved chunk by pulling its neighbors into the agent context window
- Group chunks by source document for coverage-diversification reranking
- Render a breadcrumb that includes the document title, not just the section path

Agents answering "how do I X" queries want code examples; agents answering "why was X designed this way" want prose. The retrieval pipeline can't make that distinction from current metadata.

## Behavior

All additions are **additive**. No existing key changes meaning or type. Consumers who ignore the new fields keep working.

### New metadata fields

Every `Chunk.metadata` gains these six keys, across all three chunkers:

| Key | Type | Description |
|-----|------|-------------|
| `doc_title` | `str` | The first `# heading` line of the source file, stripped of `#` and whitespace. Falls back to `Path(source_file).stem` if no H1 exists. |
| `has_code` | `bool` | `True` if the chunk content contains at least one complete fenced code block (opening and closing triple-backtick). |
| `language` | `str \| None` | The info string of the first fence if `has_code` is True and the fence carries one (e.g. `"python"` for `` ```python ``). `None` if no language specified or no code. |
| `file_id` | `str` | `sha256(source_file).hexdigest()[:12]`. Stable for the lifetime of the source file path. |
| `prev_chunk_id` | `str \| None` | `id` of the previous chunk in the same source file's chunk list. `None` for the first chunk in a file. |
| `next_chunk_id` | `str \| None` | `id` of the next chunk in the same source file's chunk list. `None` for the last chunk in a file. |

### Invariants

1. **Doc title is file-stable.** Every chunk from the same source file has the same `doc_title` and `file_id`.
2. **Chain property.** For chunks of a single source file in emission order:
   ```
   for i in range(len(chunks) - 1):
       assert chunks[i].metadata["next_chunk_id"] == chunks[i+1].metadata["id"]
       assert chunks[i+1].metadata["prev_chunk_id"] == chunks[i].metadata["id"]
   ```
3. **Code detection is conservative.** `has_code=True` requires a complete fenced block (even number of ` ``` ` markers, ≥ 2). An orphaned opening fence (from the Phase 1 oversized-split fallback) produces `has_code=False` — this is intentional; consumers shouldn't treat a fragment as code.
4. **Language lowercase, no trimming.** Fence info strings can include multiple tokens (`` ```python {linenos=true} ``). `language` is the first whitespace-delimited token, lowercased. So `` ```Python `` → `"python"`.

### Placement

All additions happen in each chunker's `_make_chunk` method, plus a new final-pass step that runs after all chunks are assembled (for `prev_chunk_id` / `next_chunk_id`).

The `Chunk` dataclass in `src/ctx/chunker/base.py` doesn't change — `metadata` is already a free-form `dict`.

### JSONL serialization

`chunks_to_jsonl` in `src/ctx/integrations/jsonl.py` already serializes `metadata` as-is. No change. New fields appear in output automatically.

## Examples

### Prose chunk

```json
{
  "id": "api-patterns/overview/authentication",
  "module": "api-patterns",
  "source_file": "content/overview.md",
  "section_path": ["Authentication"],
  "content": "## Authentication\n\nAll endpoints require JWT.",
  "metadata": {
    "tags": ["api"],
    "version": "1.0.0",
    "heading_level": 1,
    "parent_section": null,
    "token_count": 18,
    "chunk_index": 0,
    "total_chunks": 3,
    "doc_title": "API Patterns",
    "has_code": false,
    "language": null,
    "file_id": "3f2e8b9a1c4d",
    "prev_chunk_id": null,
    "next_chunk_id": "api-patterns/overview/authorization"
  }
}
```

### Code-bearing chunk

```json
{
  "id": "api-patterns/overview/request-signing",
  "content": "## Request Signing\n\n```python\ndef sign(body, secret):\n    return hmac.new(...)\n```\n\nCall this before every request.",
  "metadata": {
    "has_code": true,
    "language": "python",
    "doc_title": "API Patterns",
    ...
  }
}
```

### Multi-language chunk

A chunk with two fenced blocks (Python then Bash) reports `language: "python"` — the first fence wins. `has_code: true`. Consumers who need a language *list* can post-process the content themselves; first-fence wins is the documented contract.

## Consumer patterns enabled

1. **Parent-doc expansion.** A retriever surfaces one chunk; `file_id` groups all chunks from that doc; `prev_chunk_id`/`next_chunk_id` let the consumer expand ±N neighbors into the agent window.
2. **Code-aware boosting.** A query classifier detects "how do I…" → retriever filters for `has_code: true` or boosts those chunks in reranking.
3. **Language-specific retrieval.** Agent working on a Python codebase filters chunks to `language in ("python", None)`.
4. **Doc-level diversification.** MMR-style reranker uses `file_id` as the cluster key to avoid returning five chunks from the same doc.

None of these are implemented by ctx. The spec guarantees the metadata is present and stable; consumers build the retrieval logic.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Source file has no `#` heading anywhere | `doc_title = Path(source_file).stem.replace('_', ' ').replace('-', ' ').title()` (e.g. `"readme"` → `"Readme"`). |
| Source file has multiple H1s | Use the first one only. |
| Chunk content has three triple-backtick markers (unclosed block) | `has_code = False` (count must be even). Language is `None`. |
| Fence info includes a hyphenated language (e.g. `` ```objective-c ``) | `language = "objective-c"` (first whitespace-delimited token, lowercase). |
| Indented code block (4-space, no fence) | `has_code = False`. ctx detects fenced blocks only — indented-style code is ambiguous with markdown lists in metadata context. |
| Single-chunk file | Both `prev_chunk_id` and `next_chunk_id` are `None`. |
| Cross-file chains | Never produced. Chain is strictly within a single source file. |

## Phase 2 dependency

`doc_title` capture requires the H1-scan added by Phase 2 (`CHUNKER_ORPHAN_ELIMINATION_SPEC.md`). If Phase 2 has dropped the orphan preamble, the chunker has already seen the H1 text — it is passed through to `_make_chunk` as a kwarg. If Phase 2 hasn't shipped yet, the H1 scan must still run in this phase (the orphan drop is not required for `doc_title` to work).

## Tests (behavior)

1. **Every chunk has all six new keys.** Across all three chunkers, assert the keys are present on every emitted chunk.
2. **Chain property holds.** For chunks from a single file, walk the `prev/next_chunk_id` chain start-to-end and verify it visits every chunk in order.
3. **Multi-file chain isolation.** Module with two source files produces two separate chains; no chunk from file A points to a chunk in file B.
4. **`has_code` / `language` detection.** Fenced Python block → `(True, "python")`. Fenced no-info block → `(True, None)`. Indented code → `(False, None)`. Orphaned fence from oversized split → `(False, None)`.
5. **`doc_title` fallback.** File `notes.md` with no H1 → `doc_title = "Notes"`.
6. **`file_id` stability.** Same `source_file` string across multiple builds → same `file_id`.

## Non-Goals

- Doesn't extract symbols (function/class names) — that's AST territory, explicitly rejected in the parent plan.
- Doesn't compute semantic tags beyond what `ctx pack` already auto-infers.
- Doesn't expose a `contains_mermaid`/`contains_table` signal — `has_code` is the agreed carveout for code vs prose.
- Doesn't add a content-hash field. Callers who need one can compute it from `content`. If Phase 4's caching needs it internally, that lives in the contextualize module, not chunk metadata.
