"""Pytest configuration — isolates tests from the user's home directory.

`src/ctx/git.py` stores cloned git modules under `Path.home() / ".ctx" / "cache"`.
If a test accidentally triggered a git-ref module resolution, it would write to
the user's real home. This autouse fixture redirects `Path.home()` to a
per-test tmp dir so ctx can never escape the test sandbox.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    fake_home = tmp_path / "_fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
