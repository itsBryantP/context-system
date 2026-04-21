"""Tests for the opt-in Contextual Retrieval module (Phase 4)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ctx.chunker.base import Chunk
from ctx.chunker.contextualize import (
    ContextualizeError,
    _cache_key,
    contextualize_chunks,
)


def _make_chunk(cid: str, content: str) -> Chunk:
    return Chunk(
        id=cid,
        module="test",
        source_file="content/doc.md",
        section_path=[],
        content=content,
        metadata={},
    )


def _install_mock_anthropic(monkeypatch, responses):
    """Install a fake anthropic module that returns the given response texts in order."""
    fake_module = MagicMock()
    client = MagicMock()
    fake_module.Anthropic.return_value = client

    response_iter = iter(responses)

    def make_create(**kwargs):
        text = next(response_iter)
        resp = MagicMock()
        resp.content = [MagicMock(text=text)]
        return resp

    client.messages.create.side_effect = make_create
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return client


class TestContextualize:
    def test_prepends_context_and_sets_metadata(self, monkeypatch, tmp_path):
        client = _install_mock_anthropic(monkeypatch, ["CTX-A", "CTX-B", "CTX-C"])
        chunks = [_make_chunk(f"m/doc/{i}", f"body {i}") for i in range(3)]

        out = contextualize_chunks(
            chunks, "FULL_DOC",
            model="claude-haiku-4-5",
            cache_path=tmp_path / "cache.json",
        )

        assert len(out) == 3
        for i, (ctx, body) in enumerate([("CTX-A", "body 0"), ("CTX-B", "body 1"), ("CTX-C", "body 2")]):
            assert out[i].content.startswith(f"{ctx}\n\n")
            assert body in out[i].content
            assert out[i].metadata["situating_context"] == ctx
            assert out[i].metadata["contextualized"] is True

        assert client.messages.create.call_count == 3

    def test_cache_hit_avoids_api_call(self, monkeypatch, tmp_path):
        cache_path = tmp_path / "cache.json"

        client = _install_mock_anthropic(monkeypatch, ["CTX-1"])
        chunks = [_make_chunk("m/doc/0", "body")]
        contextualize_chunks(chunks, "DOC", model="m", cache_path=cache_path)
        assert client.messages.create.call_count == 1

        # Second call with same inputs: should hit cache, not call API.
        client2 = _install_mock_anthropic(monkeypatch, [])  # no responses — fail if called
        chunks2 = [_make_chunk("m/doc/0", "body")]
        contextualize_chunks(chunks2, "DOC", model="m", cache_path=cache_path)
        assert client2.messages.create.call_count == 0
        assert chunks2[0].metadata["situating_context"] == "CTX-1"

    def test_content_edit_invalidates_cache(self, monkeypatch, tmp_path):
        cache_path = tmp_path / "cache.json"

        _install_mock_anthropic(monkeypatch, ["CTX-OLD"])
        contextualize_chunks(
            [_make_chunk("m/doc/0", "original")], "DOC",
            model="m", cache_path=cache_path,
        )

        client = _install_mock_anthropic(monkeypatch, ["CTX-NEW"])
        chunks = [_make_chunk("m/doc/0", "edited")]
        contextualize_chunks(chunks, "DOC", model="m", cache_path=cache_path)

        assert client.messages.create.call_count == 1
        assert chunks[0].metadata["situating_context"] == "CTX-NEW"

    def test_model_change_invalidates_cache(self, monkeypatch, tmp_path):
        cache_path = tmp_path / "cache.json"

        _install_mock_anthropic(monkeypatch, ["OLD"])
        contextualize_chunks(
            [_make_chunk("m/doc/0", "body")], "DOC",
            model="haiku", cache_path=cache_path,
        )

        client = _install_mock_anthropic(monkeypatch, ["NEW"])
        contextualize_chunks(
            [_make_chunk("m/doc/0", "body")], "DOC",
            model="sonnet", cache_path=cache_path,
        )
        assert client.messages.create.call_count == 1

    def test_missing_api_key_raises(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setitem(sys.modules, "anthropic", fake)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(ContextualizeError, match="ANTHROPIC_API_KEY"):
            contextualize_chunks(
                [_make_chunk("m/doc/0", "body")], "DOC",
                model="m", cache_path=None,
            )

    def test_missing_dependency_raises(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "anthropic", None)

        with pytest.raises(ContextualizeError, match="anthropic"):
            contextualize_chunks(
                [_make_chunk("m/doc/0", "body")], "DOC",
                model="m", cache_path=None,
            )

    def test_empty_response_raises(self, monkeypatch, tmp_path):
        _install_mock_anthropic(monkeypatch, [""])
        with pytest.raises(ContextualizeError, match="empty"):
            contextualize_chunks(
                [_make_chunk("m/doc/0", "body")], "DOC",
                model="m", cache_path=tmp_path / "c.json",
            )

    def test_corrupt_cache_recovers(self, monkeypatch, tmp_path, capsys):
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("{ this is not json")

        _install_mock_anthropic(monkeypatch, ["CTX"])
        chunks = [_make_chunk("m/doc/0", "body")]
        contextualize_chunks(chunks, "DOC", model="m", cache_path=cache_path)

        captured = capsys.readouterr()
        assert "unreadable" in captured.err
        # New cache was written.
        assert json.loads(cache_path.read_text())

    def test_token_count_updated_after_prepend(self, monkeypatch, tmp_path):
        _install_mock_anthropic(monkeypatch, ["a really long situating context " * 5])
        chunks = [_make_chunk("m/doc/0", "body")]
        original_count = chunks[0].metadata.get("token_count")
        contextualize_chunks(
            chunks, "DOC", model="m", cache_path=tmp_path / "c.json"
        )
        assert chunks[0].metadata["token_count"] > (original_count or 0)


class TestCacheKey:
    def test_same_inputs_same_key(self):
        k1 = _cache_key("haiku", "doc", "chunk")
        k2 = _cache_key("haiku", "doc", "chunk")
        assert k1 == k2

    def test_model_matters(self):
        k1 = _cache_key("haiku", "doc", "chunk")
        k2 = _cache_key("sonnet", "doc", "chunk")
        assert k1 != k2

    def test_no_boundary_confusion(self):
        """sha256('a\\x00bc\\x00d') != sha256('ab\\x00c\\x00d')."""
        k1 = _cache_key("a", "bc", "d")
        k2 = _cache_key("ab", "c", "d")
        assert k1 != k2


class TestSchemaIntegration:
    def test_default_contextualize_false(self):
        from ctx.schema import ModuleConfig
        mod = ModuleConfig(name="test")
        assert mod.chunking.contextualize is False
        assert mod.chunking.contextualize_model == "claude-haiku-4-5"

    def test_contextualize_opt_in(self):
        from ctx.schema import ModuleConfig
        mod = ModuleConfig(
            name="test",
            chunking={"contextualize": True, "contextualize_model": "claude-sonnet-4-6"},
        )
        assert mod.chunking.contextualize is True
        assert mod.chunking.contextualize_model == "claude-sonnet-4-6"
