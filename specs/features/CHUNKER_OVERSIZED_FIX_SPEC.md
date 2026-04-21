# FixedChunker Oversized-Paragraph Fix — Specification

**Phase:** 1 of `plans/active/CHUNKING_IMPROVEMENTS_PLAN.md`

## Problem

`FixedChunker.chunk()` splits input on blank lines (`\n\n`) then accumulates paragraphs until they'd overflow `max_tokens`. A single paragraph larger than `max_tokens` is appended anyway and emitted as a single oversized chunk. Real-world trigger: fenced code blocks containing JSON/log/YAML dumps with no blank lines inside the block.

Observed case on the `zconfig/docs` corpus: one chunk at **1559 tokens** with `max_tokens=500` (3.1× budget), content = a single fenced block of JSON log output.

This breaks:
- **Retrieval budgeting.** An agent with a 4K retrieval budget can be forced to spend 40% of it on one chunk before ranking begins.
- **Embedding model limits.** Many embedding models cap inputs around 512–8192 tokens. A 1559-token chunk may silently truncate or error downstream.
- **ctx's own documented contract.** `max_tokens` is a user-configurable knob; violating it silently erodes trust in every other chunker guarantee.

## Behavior

### Invariant

```
For every Chunk c produced by FixedChunker:
    c.metadata["token_count"] <= max_tokens * 1.1
```

The 10% slack allows sentence-boundary preservation when the last sentence slightly exceeds the budget. No other slack is permitted.

### Algorithm

When a paragraph's token count exceeds `max_tokens`, split it using this boundary hierarchy (first match wins):

1. **Single-newline split.** Split on `\n`. If every resulting line ≤ `max_tokens`, re-accumulate lines into chunks using the same window logic (respecting `overlap_tokens` as line-level carryover).
2. **Sentence-boundary split.** Regex: `(?<=[.!?])\s+` against the paragraph text. If every resulting sentence ≤ `max_tokens`, accumulate sentences into chunks.
3. **Token-window fallback.** Encode with `get_encoder().encode()`, slide a `max_tokens`-wide window with `overlap_tokens` carryover, decode each window back to text.

A paragraph may require different strategies for different sub-parts, but the implementation may pick a single strategy per paragraph for simplicity. Only the token-window fallback is guaranteed to terminate.

### Chunk IDs for oversized splits

Each split piece becomes its own `Chunk` via `FixedChunker._make_chunk`. The existing ID scheme (`{module}/{file-stem}/{section}/{index}`) already handles this — the running `index` is incremented per emitted chunk, so splitting one paragraph into three pieces yields three consecutive indices. No new ID rules needed.

### Fenced code block behavior

The fix does **not** attempt to re-emit opening/closing triple-backtick fences per sub-chunk. If a 1500-token fenced block is split into three pieces:

- Piece 1 contains the opening ` ``` ` fence and the first third of the code.
- Pieces 2 and 3 contain middle/end code only — no fences.
- Piece 3 contains the closing ` ``` ` fence.

Retrievers that surface a single piece in isolation see ill-formed markdown. This is an acceptable tradeoff: correctness of the `max_tokens` contract matters more than cosmetic fence balance. A future enhancement could annotate `metadata.partial_code_block: true`; out of scope for this phase.

## API

### New private helper

```python
def _split_oversized_paragraph(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Split a paragraph that exceeds max_tokens into pieces, each ≤ max_tokens.

    Tries, in order: single-newline split, sentence-boundary split,
    token-window split. Returns non-empty list; each element's
    count_tokens(element) <= max_tokens.
    """
```

### Call site in `FixedChunker.chunk()`

```python
for para in paragraphs:
    para_tokens = count_tokens(para)

    if para_tokens > max_tokens:
        # Flush current chunk if any — oversized paragraphs don't merge.
        if current_paragraphs:
            chunks.append(self._make_chunk(
                "\n\n".join(current_paragraphs),
                section_path, len(chunks),
                module_name=module_name, source_file=source_file,
                tags=tags, version=version,
            ))
            current_paragraphs, current_tokens = [], 0

        for piece in _split_oversized_paragraph(para, max_tokens, overlap_tokens):
            chunks.append(self._make_chunk(
                piece, section_path, len(chunks),
                module_name=module_name, source_file=source_file,
                tags=tags, version=version,
            ))
        continue

    # existing logic unchanged
    ...
```

## Edge Cases

| Input | Expected output |
|-------|-----------------|
| Paragraph exactly `max_tokens + 1` tokens | 2 chunks, each ≤ `max_tokens` |
| Paragraph with no `\n`, no `.`, no `!`, no `?` (e.g. base64 blob) | Token-window fallback; each chunk ≤ `max_tokens` |
| Paragraph that is already ≤ `max_tokens` | Unchanged (existing code path) |
| Paragraph with a single sentence > `max_tokens` | Token-window fallback applied to that sentence |
| Multiple consecutive oversized paragraphs | Each split independently; no cross-paragraph merging |
| Empty paragraph after `.strip()` | Skipped by the existing `if p.strip()` filter in `FixedChunker.chunk` (no change needed) |

## Tests (behavior, not implementation)

1. **Normal paragraphs unaffected.** Give `FixedChunker` a document where every paragraph is well under `max_tokens`; output matches pre-fix byte-for-byte (except for chunk count metadata fields if any change in Phase 3).
2. **Single oversized paragraph splits.** 2000-token paragraph with only internal newlines → multiple chunks, `max(token_counts) ≤ max_tokens`.
3. **Oversized with no breakpoints.** 2000-token string with no `\n`, no sentence enders → multiple chunks via token-window fallback.
4. **Boundary preservation preferred.** 900-token paragraph with 10 internal newlines → split at newline boundaries rather than mid-line.
5. **Real corpus regression.** After running `ctx pack` against `zconfig/docs`, `max(token_counts) ≤ 550` across all 147+ chunks.

## Non-Goals

- Re-emitting code fences per sub-chunk (future enhancement, not this phase).
- Changing heuristics for the *normal* paragraph path (the one that's not oversized).
- Changing `HeadingChunker` — it delegates to `FixedChunker._fixed_fallback` for oversized sections and inherits this fix transparently.
