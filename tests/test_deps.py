"""Tests for dependency resolution."""

from __future__ import annotations

import pytest

from ctx.deps import check_dependencies, parse_dep


class TestParseDep:
    def test_name_only(self):
        name, version = parse_dep("api-patterns")
        assert name == "api-patterns"
        assert version is None

    def test_name_and_version(self):
        name, version = parse_dep("api-patterns@1.0.0")
        assert name == "api-patterns"
        assert version == "1.0.0"

    def test_name_with_range(self):
        name, version = parse_dep("api-patterns@^1.0")
        assert name == "api-patterns"
        assert version == "^1.0"

    def test_strips_whitespace(self):
        name, _ = parse_dep("  my-module  ")
        assert name == "my-module"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid dependency"):
            parse_dep("org/repo")  # slashes not allowed in name


class TestCheckDependencies:
    def test_all_met(self):
        unmet = check_dependencies(["api-patterns", "org-glossary"], {"api-patterns", "org-glossary"})
        assert unmet == []

    def test_one_unmet(self):
        unmet = check_dependencies(["api-patterns", "missing-mod"], {"api-patterns"})
        assert unmet == ["missing-mod"]

    def test_all_unmet(self):
        unmet = check_dependencies(["a", "b"], set())
        assert set(unmet) == {"a", "b"}

    def test_empty_depends_on(self):
        assert check_dependencies([], {"anything"}) == []

    def test_version_ignored_for_name_check(self):
        unmet = check_dependencies(["api-patterns@^1.0"], {"api-patterns"})
        assert unmet == []
