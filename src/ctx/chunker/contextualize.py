"""Optional Contextual Retrieval — prepend LLM-generated situating context to chunks.

Reference: https://www.anthropic.com/news/contextual-retrieval

Behavior is described in specs/features/CONTEXTUAL_RETRIEVAL_SPEC.md.
Only invoked when `chunking.contextualize: true` is set in module.yaml.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from ctx.chunker.base import Chunk


_PROMPT_SUFFIX = (
    "\n\nHere is the chunk we want to situate within the whole document:\n\n"
    "<chunk>\n{chunk_content}\n</chunk>\n\n"
    "Please give a short succinct context to situate this chunk within the "
    "overall document for the purposes of improving search retrieval of the "
    "chunk. Answer only with the succinct context and nothing else."
)


class ContextualizeError(Exception):
    """Base error for contextualize failures surfaced to the CLI."""


def contextualize_chunks(
    chunks: list[Chunk],
    full_doc: str,
    *,
    model: str = "claude-haiku-4-5",
    cache_path: Path | None = None,
) -> list[Chunk]:
    """Mutate chunks in place: prepend situating context, set metadata.

    Raises:
        ContextualizeError: on missing anthropic package, missing API key,
            empty model response, or API failure.
    """
    anthropic = _import_anthropic()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ContextualizeError(
            "ANTHROPIC_API_KEY is not set. Set it in your environment or "
            "disable contextualize in module.yaml."
        )

    cache = _load_cache(cache_path) if cache_path else {}
    client = anthropic.Anthropic()

    for chunk in chunks:
        key = _cache_key(model, full_doc, chunk.content)
        entry = cache.get(key)

        if entry is not None:
            context = entry["context"]
        else:
            context = _call_api(client, model, full_doc, chunk.content)
            cache[key] = {"context": context, "model": model}

        chunk.content = f"{context}\n\n{chunk.content}"
        chunk.metadata["situating_context"] = context
        chunk.metadata["contextualized"] = True
        # Re-count tokens since content changed.
        from ctx.chunker.base import count_tokens
        chunk.metadata["token_count"] = count_tokens(chunk.content)

    if cache_path:
        _save_cache(cache_path, cache)

    return chunks


def _import_anthropic():
    """Lazy import with a clear install hint on failure."""
    try:
        import anthropic
    except ImportError as e:
        raise ContextualizeError(
            "contextualize requires the 'anthropic' package. "
            "Install with: uv pip install 'ctx-modules[contextualize]'"
        ) from e
    if anthropic is None:  # monkeypatched-out in tests
        raise ContextualizeError(
            "contextualize requires the 'anthropic' package. "
            "Install with: uv pip install 'ctx-modules[contextualize]'"
        )
    return anthropic


def _cache_key(model: str, full_doc: str, chunk_content: str) -> str:
    data = (model + "\x00" + full_doc + "\x00" + chunk_content).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(
            f"warning: contextualize cache at {path} is unreadable ({e}); "
            "starting with empty cache",
            file=sys.stderr,
        )
        return {}


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _call_api(client, model: str, full_doc: str, chunk_content: str) -> str:
    """Call the Anthropic API with prompt caching on the full-doc prefix."""
    doc_block = {
        "type": "text",
        "text": f"<document>\n{full_doc}\n</document>",
        "cache_control": {"type": "ephemeral"},
    }
    user_block = {
        "type": "text",
        "text": _PROMPT_SUFFIX.format(chunk_content=chunk_content),
    }
    try:
        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": [doc_block, user_block]}],
        )
    except Exception as e:
        raise ContextualizeError(f"Anthropic API call failed: {e}") from e

    text = response.content[0].text.strip() if response.content else ""
    if not text:
        raise ContextualizeError("Model returned an empty situating context")
    return text
