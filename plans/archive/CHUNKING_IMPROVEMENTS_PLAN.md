# Chunking Improvements — Implementation Plan

## Overview

Four changes driven by the evaluation in `prompts/chunking-evaluation-prompt.md`. Each phase has a full specification under `specs/features/`:

1. **Fix oversized-paragraph bug in `FixedChunker`** (`specs/features/CHUNKER_OVERSIZED_FIX_SPEC.md`) — single paragraphs larger than `max_tokens` are currently emitted as-is, violating the chunker's budget contract.
2. **Eliminate title-only orphan chunks** (`specs/features/CHUNKER_ORPHAN_ELIMINATION_SPEC.md`) — roughly 10% of chunks on real corpora are just a bare H1 or H2 header with no body; these are retrieval noise.
3. **Hierarchical-retrieval metadata hints** (`specs/features/CHUNKER_METADATA_SPEC.md`) — add `doc_title`, `has_code`, `language`, `prev_chunk_id`, `next_chunk_id`, `file_id` to metadata so RAG consumers can implement parent-expansion or code-aware filtering without ctx taking on that complexity.
4. **Opt-in Contextual Retrieval** (`specs/features/CONTEXTUAL_RETRIEVAL_SPEC.md`) — new `chunking.contextualize` flag that prepends an LLM-generated situating sentence to each chunk before output.

Phases 1–3 are pure-code changes and preserve ctx's "zero-LLM at build time" default. Phase 4 introduces an optional dependency path and ships behind a flag that defaults off.

### Design principles preserved

- **Deterministic by default.** Only Phase 4 introduces non-determinism, and only when explicitly enabled and keyed by content hash for caching.
- **Dependency-light.** Phases 1–3 add no new runtime deps. Phase 4 adds `anthropic` as an *optional* extra, not a core requirement.
- **Additive metadata.** No existing metadata keys change meaning. Existing consumers keep working.

### Explicitly out of scope

| Alternative | Why not |
|-------------|---------|
| Late chunking | Requires long-context embedding models and shifts ctx's "consumer supplies embeddings" contract. |
| Full semantic / agentic chunking as a default | Non-deterministic LLM boundary choices break freshness tracking. Possible future opt-in experimental strategy but not in this plan. |
| AST-aware code chunking | Per-language parser complexity for a markdown-first tool. Different problem space. |

---

## Phases

### Phase 1 — Fix oversized-paragraph bug in `FixedChunker`

**Goal:** No chunk ever exceeds `max_tokens * 1.1` (small slack for sentence-boundary preservation).

**Root cause recap:** `src/ctx/chunker/fixed.py:33-51` splits on `\n\n` then appends each paragraph whole — so a single paragraph bigger than `max_tokens` (e.g. a code block without blank lines, a JSON log dump) becomes one monolithic chunk.

| # | What | Details |
|---|------|---------|
| 1 | Add `_split_oversized_paragraph(text, max_tokens, overlap_tokens) -> list[str]` helper | Private helper in `fixed.py`. Tries boundary hierarchy in order: (a) single newlines (`\n`) for code blocks; (b) sentence endings (`. `, `! `, `? `) for prose; (c) token-window fallback using `get_encoder().encode()`/`.decode()` with `overlap_tokens` carryover. Return list of strings each ≤ `max_tokens`. |
| 2 | Call helper in main loop | When `para_tokens > max_tokens`: flush current chunk if any, then emit each split piece as its own chunk. Do not roll the split pieces back into normal paragraph accumulation. |
| 3 | `HeadingChunker._fixed_fallback` inherits the fix automatically | No change needed — it delegates to `FixedChunker.chunk()`. |

**Tests (`tests/test_chunker.py`):**
- A 2000-token single paragraph (no blank lines) produces multiple chunks, each ≤ `max_tokens`.
- A 1500-token code block (` ``` ` fences, no blank lines inside) produces multiple chunks; the opening fence lands in the first chunk and the closing fence in the last (document the known-imperfect behavior: we don't re-emit fences per sub-chunk).
- Existing paragraph-boundary tests still pass — normal-sized paragraphs unchanged.
- Regression test against the real zconfig corpus: assert `max(token_counts) <= 550` after rebuild.

**Files touched:** `src/ctx/chunker/fixed.py`, `tests/test_chunker.py`.

---

### Phase 2 — Eliminate title-only orphan chunks

**Goal:** No chunk is emitted consisting only of a heading line (or heading + blank lines). Heading context is preserved via `section_path` and the new `doc_title` metadata (added in Phase 3).

Two separate cases:

**Case A: file-level H1 preamble becomes an orphan.** When a file starts with an H1 and the first H2 immediately follows, `HeadingChunker._split_at_level` emits `[([], "# Title")]` as the preamble section. Example: `docs/discovery` produced a 5-token chunk containing only `"# CICS Discovery Architecture"`.

**Case B: H2 with no body, only H3 subsections.** An H2 section whose immediate body is empty (before the first H3) emits the H2 header as its own micro-chunk. Example: `eval-real/claude/key-conventions` (4 tokens, content `"## Key Conventions"`).

| # | What | Details |
|---|------|---------|
| 4 | Add `_is_orphan_heading(content: str) -> bool` helper | `src/ctx/chunker/heading.py`. Returns True if content, after stripping whitespace, consists only of lines starting with `#` (any level). |
| 5 | Drop orphan preamble in `_split_at_level` | In `heading.py:95-98`, after computing `preamble`, call `_is_orphan_heading(preamble)`; if True, don't append to `sections`. Capture the H1 text for step 7. |
| 6 | Skip orphan H2 sections when they have H3 subsections | After splitting at the requested level, if a section's content is an orphan heading AND a deeper-level split would produce more than one sub-section, skip the parent and emit only the children (with the H2 carried in `section_path`, which already happens). |
| 7 | Capture doc title for metadata | Pull the first `# heading` line from the original content (before any splits). Pass it to `_make_chunk` as a new optional kwarg `doc_title`. Used by Phase 3. |

**Tests (`tests/test_chunker.py`):**
- A markdown doc with structure `# Title / ## A / ## B` (no body between `# Title` and `## A`) produces 2 chunks (A and B), not 3. Both chunks' metadata carries `doc_title == "Title"`.
- A markdown doc with `## Parent / ### Sub1 / ### Sub2` where Parent has no body produces chunks for Sub1 and Sub2 only, with `section_path == ["Parent", "Sub1"]` and `["Parent", "Sub2"]` respectively.
- A markdown doc with `# Title / Prose / ## Section` produces a preamble chunk containing "Prose" (but prefixed by the title — verify H1 is still visible for retrieval context).
- Regression on zconfig corpus: assert `min(token_counts) >= 20` after rebuild (no more 2–10 token orphans).

**Files touched:** `src/ctx/chunker/heading.py`, `tests/test_chunker.py`.

---

### Phase 3 — Hierarchical-retrieval metadata hints

**Goal:** Give RAG consumers the fields they need for parent-expansion and code-aware filtering without ctx implementing either workflow itself.

| # | What | Details |
|---|------|---------|
| 8 | Add `doc_title` to metadata | Populated in Phase 2. Falls back to file stem if the doc has no H1. |
| 9 | Detect code blocks in `_make_chunk` | Count ` ``` ` fences. If even count ≥ 2 and chunk content contains a fenced block, set `has_code: true`. Extract the language from the first fence's info string (`` ```python `` → `language: "python"`). Leave `null` if no fence info. |
| 10 | Add `prev_chunk_id` / `next_chunk_id` | Populate in the final pass of each chunker (same loop that sets `chunk_index` / `total_chunks`). The first chunk has `prev_chunk_id: null`; the last has `next_chunk_id: null`. |
| 11 | Add `file_id` | `hashlib.sha256(source_file.encode()).hexdigest()[:12]`. Enables consumers to group chunks by source file without string-matching paths. |
| 12 | Bump JSONL emitter | `src/ctx/integrations/jsonl.py` already serializes `metadata` as-is, so no change — just verify nothing hardcoded the expected shape. |

**Tests:**
- In `tests/test_chunker.py`: new chunks have `doc_title`, `file_id`, `prev_chunk_id`, `next_chunk_id`, `has_code`, `language` fields. For a chunk with a fenced Python block, `has_code == True` and `language == "python"`. For a prose-only chunk, `has_code == False` and `language is None`.
- Chain property: for the chunks of a single file, `chunks[i].metadata["next_chunk_id"] == chunks[i+1].metadata["prev_chunk_id"]`.
- In `tests/test_pack.py`: existing JSONL serialization tests continue to pass; add one assertion that `doc_title` is present.

**Files touched:** `src/ctx/chunker/base.py` (Chunk dataclass — nothing needed, metadata dict stays dict), `src/ctx/chunker/heading.py`, `src/ctx/chunker/fixed.py`, `src/ctx/chunker/definition.py`, `tests/test_chunker.py`, `tests/test_definition_chunker.py`.

---

### Phase 4 — Opt-in Contextual Retrieval

**Goal:** Optional flag that prepends one LLM-generated situating sentence to each chunk before output. Defaults off. Zero effect on users who don't enable it.

Reference: Anthropic's Contextual Retrieval (https://www.anthropic.com/news/contextual-retrieval) — reported ~35% reduction in failed retrievals on docs-style corpora.

| # | What | Details |
|---|------|---------|
| 13 | Schema change — `ChunkingConfig.contextualize` | `src/ctx/schema.py`. Add `contextualize: bool = False`. Also add `contextualize_model: str = "claude-haiku-4-5"` for future flexibility. |
| 14 | Optional dependency | `pyproject.toml`: add new extra `contextualize = ["anthropic>=0.40"]`. Do not add to core deps. |
| 15 | New module `src/ctx/chunker/contextualize.py` | Exposes `contextualize_chunks(chunks: list[Chunk], full_doc: str, model: str) -> list[Chunk]`. For each chunk, call Anthropic API with a prompt that includes the full doc (marked `<cache_control>`) and the chunk, asks for a 1–2 sentence situating context, prepends the response to `chunk.content`. Uses prompt caching for the full-doc prefix so only the chunk varies per call. |
| 16 | Content-hash caching | Before making an LLM call for a chunk, check a cache keyed by `sha256(full_doc + chunk.content)`. Cache file at `.context/.contextualize-cache.json` (gitignore-safe). Hit → skip LLM call, use cached context string. Miss → call, store. Preserves incremental-rebuild story. |
| 17 | Wire into `_build_module` | `src/ctx/cli.py`: after chunking, if `mod.chunking.contextualize` is True, import `contextualize_chunks` (inside the if branch so the import failure on missing `anthropic` is lazy and only affects users who enable the flag). Pass the full source file text as `full_doc`. |
| 18 | Handle missing dependency | If `contextualize: true` but `anthropic` isn't installed, raise `click.ClickException` with install hint: `uv pip install 'ctx-modules[contextualize]'`. Also require `ANTHROPIC_API_KEY` env var; fail fast with a clear message if missing. |
| 19 | Store situating context in metadata | In addition to prepending to `content`, set `metadata.situating_context: str` so consumers who want to embed raw-chunk + context separately can. |
| 20 | Config docs | Update `CLAUDE.md` and `README.md` with a dedicated "Contextual Retrieval" section: when to use it, cost estimate (~$0.15 per 150-chunk corpus rebuild with prompt caching), env var setup. |

**Tests (`tests/test_contextualize.py` — new):**
- With `anthropic` mocked: input 3 chunks, verify each chunk's content is prefixed with a mock context string and `metadata.situating_context` is populated.
- Cache hit: on second call with identical input, no API call is made (assert mock call count).
- Cache invalidation: if a chunk's content changes, the cache miss triggers a new API call.
- Without the `contextualize` extra installed: import of `ctx.chunker.contextualize` at call time raises a friendly error (test via `monkeypatch.setitem(sys.modules, "anthropic", None)`).
- Schema test: `ModuleConfig` accepts `chunking: {contextualize: true}` and defaults to `false` otherwise.

**Files touched:** `src/ctx/schema.py`, `src/ctx/cli.py`, `src/ctx/chunker/contextualize.py` (new), `pyproject.toml`, `CLAUDE.md`, `README.md`, `tests/test_contextualize.py` (new), `tests/test_schema.py`.

---

## Ordering and Dependencies

1. **Phase 1 first** — standalone bugfix, smallest blast radius. Ship independently.
2. **Phase 2 second** — depends on nothing, but changes chunk count on real corpora, so worth shipping separately so any downstream index invalidation is obvious in git blame.
3. **Phase 3 third** — pure additive metadata, no-op for existing consumers. Depends on Phase 2 for the `doc_title` capture (step 7).
4. **Phase 4 last** — biggest change, optional path. Built on top of the metadata additions from Phase 3 (reuses `situating_context` as a metadata field).

Each phase ends with a green `pytest` run (297+ current tests, plus new ones) and an explicit assertion that nothing in `~/.ctx` was created during test runs (per `tests/conftest.py` home isolation).

## Rollout Checks

After each phase, re-run the evaluation corpus and confirm:

```bash
.venv-test/bin/ctx pack /Users/bpanyar/github/IBMZSoftware/zconfig/docs -o .eval-zconfig
python3 -c "
import json
chunks = [json.loads(l) for l in open('.eval-zconfig/chunks/docs.jsonl')]
tks = [c['metadata']['token_count'] for c in chunks]
print(f'chunks={len(chunks)} max_tok={max(tks)} min_tok={min(tks)} orphans={sum(1 for t in tks if t < 30)}')
"
```

Expected progression:
- **Before:** `chunks=147 max_tok=1559 min_tok=2 orphans=15`
- **After Phase 1:** `max_tok <= 550`
- **After Phase 2:** `orphans == 0`, `min_tok >= 20`, chunk count drops ~10%
- **After Phase 3:** `metadata` includes `doc_title`, `has_code`, `prev_chunk_id`, `next_chunk_id`, `file_id`
- **After Phase 4 (with flag enabled):** first line of each chunk is a situating sentence; `metadata.situating_context` populated; rebuild with no content changes makes zero API calls.

## Non-Goals for This Plan

- Don't restructure the `Chunk` dataclass — metadata stays a free-form dict for now.
- Don't change existing chunk IDs. All changes preserve the current ID scheme.
- Don't migrate existing chunker tests to new file locations — the flat `tests/` layout stays.
- Don't rewrite the definition chunker's orphan handling even though it uses a similar pattern — definition chunks are already term-keyed and rarely produce title-only outputs. Revisit only if evaluation on a glossary-style corpus shows the same issue.
