# Contextual Retrieval — Specification

**Phase:** 4 of `plans/active/CHUNKING_IMPROVEMENTS_PLAN.md`

## Problem

Chunks routinely lose the context they had in the source document. A section titled "Configuration" in a doc about CICS means something very different from one in a doc about network routing, but the chunk content alone doesn't encode the difference. Embedding models score these by surface content only. An agent querying "how do I configure retry timeouts" gets any `Configuration` section that mentions retry or timeout — regardless of whether it's the right subsystem.

Anthropic's Contextual Retrieval technique (https://www.anthropic.com/news/contextual-retrieval) addresses this by prepending an LLM-generated 1–2 sentence situating context to each chunk before embedding. Reported ~35% reduction in failed retrievals on docs corpora.

ctx should support this as an **opt-in** feature: zero impact on users who don't enable it, straightforward to enable per module.

## Behavior

### Opt-in via schema

`ChunkingConfig` gains two fields (both default off / sensible):

```yaml
chunking:
  strategy: heading
  contextualize: true              # default: false
  contextualize_model: claude-haiku-4-5  # default; user may override
```

When `contextualize: false` (the default), this phase has zero runtime effect.

### What the flag does

After normal chunking produces `list[Chunk]`, each chunk passes through:

1. A cache lookup keyed by `sha256(full_doc_text + chunk.content).hexdigest()`.
2. On **hit**, the cached situating context string is used directly.
3. On **miss**, a single LLM call is made with the full document in a cached prompt prefix and the chunk in the user message. The response is stored to cache and used.
4. The situating context is **prepended** to `chunk.content` with a blank line separator, and also stored verbatim in `chunk.metadata["situating_context"]`.

### Mutation of `chunk.content`

```
# Before contextualize
chunk.content = "## Authentication\n\nUse JWT tokens..."

# After contextualize
chunk.content = "This chunk describes the authentication mechanism used across the API Patterns module, where JWT is the required token format.\n\n## Authentication\n\nUse JWT tokens..."
```

Both the prepended context and the original content flow through to JSONL output. Downstream embeddings embed the combined string — that's the point.

### Metadata field

`chunk.metadata["situating_context"]: str` holds the raw LLM output (without the prepended content). Consumers who want to embed the original chunk and the context as separate vectors can do so.

`chunk.metadata["contextualized"]: bool` — always `True` when the contextualize path ran, `False` (or absent) otherwise.

## Configuration

### Schema — `ChunkingConfig` (new fields)

```python
class ChunkingConfig(BaseModel):
    # existing fields unchanged
    contextualize: bool = False
    contextualize_model: str = "claude-haiku-4-5"
```

No other schema changes. `ProjectConfig` and `ModuleConfig` are untouched.

### Dependency — `pyproject.toml`

```toml
[project.optional-dependencies]
contextualize = ["anthropic>=0.40"]
```

Core install does **not** pull in `anthropic`. Users who want this feature install with:

```bash
uv pip install 'ctx-modules[contextualize]'
# or
uv sync --extra contextualize
```

### Required env var

`ANTHROPIC_API_KEY` must be set when `contextualize: true`. Checked at `_build_module` entry, not at module import. Error message if missing:

```
ctx: contextualize is enabled for module '<name>' but ANTHROPIC_API_KEY is not set.
Set it in your environment or disable contextualize in module.yaml.
```

## LLM Prompt

A fixed prompt template, not user-configurable (for determinism across rebuilds):

```
<document>
{full_doc_text}
</document>

Here is the chunk we want to situate within the whole document:

<chunk>
{chunk_content}
</chunk>

Please give a short succinct context to situate this chunk within the overall
document for the purposes of improving search retrieval of the chunk. Answer
only with the succinct context and nothing else.
```

The `<document>` block is placed in a `cache_control: {"type": "ephemeral"}` content block. For a module with N chunks from the same source file, the document text is cached once and reused N-1 times — Anthropic's prompt cache has 5-minute TTL, well within a single build.

### Model defaults

- `contextualize_model` default: `"claude-haiku-4-5"` (current Haiku generation, cheapest).
- Users who want higher quality can set `contextualize_model: "claude-sonnet-4-6"` in their `module.yaml`.
- The model string is passed through verbatim to the Anthropic SDK; no validation beyond what the SDK does.

### Token budget

- Max 100 output tokens per call. Responses are 1–2 sentences by design; cap enforces the contract.
- No max_input_tokens — relies on the caller to not chunk documents larger than the model's input limit.

## Cache

### File format

`.context/.contextualize-cache.json` — a plain JSON object:

```json
{
  "<sha256-hex>": {
    "context": "This chunk describes...",
    "model": "claude-haiku-4-5",
    "created_at": "2026-04-21T10:00:00Z",
    "input_tokens": 1834,
    "output_tokens": 42
  }
}
```

### Key derivation

```python
cache_key = hashlib.sha256(
    (full_doc_text + "\x00" + chunk_content).encode("utf-8")
).hexdigest()
```

The null byte separator prevents boundary confusion (e.g. `A+BC` vs `AB+C`). Includes full doc text so that editing the doc invalidates all its chunks' contexts, not just the edited chunk's.

### Invalidation rules

- **Content edit** in the source file → new `full_doc_text` → different cache key → miss → re-call.
- **Model change** (`contextualize_model` updated in `module.yaml`) → cache entries still keyed by `(doc, chunk)` → would reuse stale contexts. Fix: include `model` in the key:
  ```python
  cache_key = hashlib.sha256(
      (model + "\x00" + full_doc + "\x00" + chunk).encode("utf-8")
  ).hexdigest()
  ```
- **Prompt template change** (future) → bump a version constant and include in key.

### Cache location

Lives under `.context/` (same directory as freshness metadata). Gitignore pattern `.context/chunks/` already covers it via parent `.context/` if the user so chooses, but the cache file itself is safe to commit — it's just a materialized optimization.

### Cache is per-project, not per-user

Contrast with `~/.ctx/cache/` (git clones). The contextualize cache lives in the project because its contents are module-specific and editor-synced. Multiple checkouts of the same module can share the cache via git or regenerate locally.

## Wire-in

### In `src/ctx/cli.py::_build_module`

After the existing chunking loop produces `all_chunks`:

```python
if mod.chunking.contextualize:
    from ctx.chunker.contextualize import contextualize_chunks  # lazy import

    # Rebuild per-file so each chunk sees its own full_doc.
    # This means contextualize runs inside the inner chunking loop, not here.
    # Alternative: pass the file → content map out of the loop and contextualize
    # in one batch. Implementation detail; spec-wise the outcome is identical.
    ...
```

The exact placement is a plan-level concern. Spec requires only: every emitted chunk whose module has `contextualize: true` has a non-empty `metadata["situating_context"]` and a content prefix matching that string.

### Missing dependency handling

If `contextualize: true` but the `anthropic` package isn't installed, the import at the top of `contextualize_chunks` fails. Wrap the lazy import:

```python
try:
    from ctx.chunker.contextualize import contextualize_chunks
except ImportError as e:
    raise click.ClickException(
        "contextualize is enabled but 'anthropic' is not installed. "
        "Install with: uv pip install 'ctx-modules[contextualize]'"
    ) from e
```

## Cost Model

For a typical module with one source file of ~10K tokens and 50 chunks:

- First chunk: full doc in prompt, ~10K input tokens, ~50 output tokens.
- Chunks 2–50: doc cached, ~200 input (chunk + prompt scaffolding) + ~50 output each.
- Per-chunk cached cost (Haiku 4.5): roughly $0.80/1M input × 200 + $4/1M output × 50 ≈ $0.0004.
- First-chunk (cache miss): $0.80/1M × 10000 + $4/1M × 50 ≈ $0.008.
- **Total for 50 chunks: ~$0.03.**

For the zconfig corpus (24 docs, 147 chunks): rough estimate ~$0.15 at full rebuild. `ctx build` freshness skipping means only edited modules re-run, so amortized cost over a working session is near-zero.

Document these numbers in `CLAUDE.md` and `README.md` so users can decide.

## Determinism and Incremental Builds

Contextual Retrieval is **deterministic given a fixed cache**. The cache key includes document text, chunk text, and model; identical inputs produce identical outputs (the LLM call is replayed from cache). Freshness tracking and incremental rebuilds work unchanged.

First build is non-deterministic at the LLM level (different runs of the same prompt can produce different situating contexts), but cached afterward. For reproducible-build users, recommend committing `.context/.contextualize-cache.json`.

## Error Handling

| Failure | Behavior |
|---------|----------|
| `ANTHROPIC_API_KEY` unset | `ClickException` at build entry with clear instruction. |
| `anthropic` package missing | `ClickException` with install hint. |
| API request fails (network, rate limit, etc.) | Raise. Do NOT fall back to un-contextualized chunks silently — that would drift behavior invisibly. User can retry or disable the flag. |
| Cache file corrupt (JSON parse error) | Warn, treat as empty cache, overwrite on next write. |
| Model returns empty string | Raise — indicates a prompt or model issue worth surfacing. |

## Tests (behavior)

All tests mock the Anthropic client — no real API calls in the test suite.

1. **Default off.** Module without `contextualize: true` produces chunks with no `situating_context` in metadata and no content mutation.
2. **Flag on, content prepended.** With a stubbed client that returns `"MOCK CONTEXT"`, each chunk's content starts with `"MOCK CONTEXT\n\n"` and `metadata["situating_context"] == "MOCK CONTEXT"`.
3. **Cache hit avoids API call.** Run once, snapshot cache, run again with same inputs — assert `client.messages.create` call count unchanged from snapshot.
4. **Content edit invalidates cache.** Change one character in the source file, rebuild — assert new API calls for chunks from that file only.
5. **Model change invalidates cache.** Change `contextualize_model`, rebuild — assert all cached entries re-generated.
6. **Missing API key.** Unset `ANTHROPIC_API_KEY`, run build → `ClickException`.
7. **Missing dependency.** `sys.modules["anthropic"] = None` (monkeypatch), run build → `ClickException` with install hint.
8. **Cache file resilience.** Corrupt `.context/.contextualize-cache.json` (e.g. write `"{ broken"`), run build → warning emitted, new cache created with all entries from this run.

## Non-Goals

- No streaming output. Contextualize calls are short (< 100 tokens); streaming adds complexity for no user-visible benefit.
- No batch API usage. Batch is slower and less predictable for interactive builds; prompt caching already amortizes cost.
- No pluggable LLM provider. `anthropic` only. A future phase could add OpenAI/etc. if demand materializes.
- No automatic fallback to un-contextualized output on API error. Silent behavior drift is worse than an explicit failure.
- No per-chunk override of the prompt template. Determinism requires a fixed prompt.
