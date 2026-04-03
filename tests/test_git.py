"""Tests for git URL module resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ctx.git import cache_path, parse_git_ref, resolve_git_module


class TestParseGitRef:
    def test_bare_url(self):
        url, subdir, ref = parse_git_ref("https://github.com/org/repo.git")
        assert url == "https://github.com/org/repo.git"
        assert subdir is None
        assert ref is None

    def test_url_with_subdir(self):
        url, subdir, ref = parse_git_ref("https://github.com/org/repo.git#modules/api")
        assert url == "https://github.com/org/repo.git"
        assert subdir == "modules/api"
        assert ref is None

    def test_url_with_ref(self):
        url, subdir, ref = parse_git_ref("https://github.com/org/repo.git@v1.0")
        assert url == "https://github.com/org/repo.git"
        assert subdir is None
        assert ref == "v1.0"

    def test_url_with_subdir_and_ref(self):
        url, subdir, ref = parse_git_ref("https://github.com/org/repo.git#modules/api@v2.0")
        assert url == "https://github.com/org/repo.git"
        assert subdir == "modules/api"
        assert ref == "v2.0"

    def test_url_with_branch_ref(self):
        url, subdir, ref = parse_git_ref("https://github.com/org/repo.git@main")
        assert ref == "main"
        assert subdir is None


class TestCachePath:
    def test_returns_path_under_home(self):
        p = cache_path("https://github.com/org/repo.git", "v1.0")
        assert str(p).startswith(str(Path.home()))
        assert ".ctx/cache" in str(p)

    def test_different_refs_different_paths(self):
        p1 = cache_path("https://github.com/org/repo.git", "v1.0")
        p2 = cache_path("https://github.com/org/repo.git", "v2.0")
        assert p1 != p2

    def test_same_inputs_same_path(self):
        p1 = cache_path("https://github.com/org/repo.git", "main")
        p2 = cache_path("https://github.com/org/repo.git", "main")
        assert p1 == p2

    def test_none_ref_stable(self):
        p1 = cache_path("https://github.com/org/repo.git", None)
        p2 = cache_path("https://github.com/org/repo.git", None)
        assert p1 == p2


class TestResolveGitModule:
    def test_clones_when_not_cached(self, tmp_path):
        git_ref = "https://github.com/org/repo.git"

        with patch("ctx.git.cache_path", return_value=tmp_path / "cache") as mock_cp, \
             patch("ctx.git._clone") as mock_clone:
            # Simulate clone creating the directory
            def fake_clone(repo, ref, dest):
                dest.mkdir(parents=True, exist_ok=True)
            mock_clone.side_effect = fake_clone

            result = resolve_git_module(git_ref)

        mock_clone.assert_called_once()
        assert result == tmp_path / "cache"

    def test_skips_clone_when_cached(self, tmp_path):
        cached = tmp_path / "cache"
        cached.mkdir()

        with patch("ctx.git.cache_path", return_value=cached), \
             patch("ctx.git._clone") as mock_clone:
            resolve_git_module("https://github.com/org/repo.git")

        mock_clone.assert_not_called()

    def test_returns_subdir(self, tmp_path):
        cached = tmp_path / "cache"
        subdir = cached / "modules" / "api"
        subdir.mkdir(parents=True)

        with patch("ctx.git.cache_path", return_value=cached):
            result = resolve_git_module(
                "https://github.com/org/repo.git#modules/api"
            )

        assert result == subdir

    def test_raises_when_subdir_missing(self, tmp_path):
        cached = tmp_path / "cache"
        cached.mkdir()

        with patch("ctx.git.cache_path", return_value=cached):
            with pytest.raises(FileNotFoundError, match="modules/missing"):
                resolve_git_module(
                    "https://github.com/org/repo.git#modules/missing"
                )

    def test_clone_failure_raises_runtime_error(self, tmp_path):
        with patch("ctx.git.cache_path", return_value=tmp_path / "cache"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="fatal: repo not found")

            with pytest.raises(RuntimeError, match="git clone failed"):
                resolve_git_module("https://github.com/org/bad-repo.git")
