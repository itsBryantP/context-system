"""Dependency resolution for ctx modules."""

from __future__ import annotations

import re

_DEP_RE = re.compile(r"^(?P<name>[a-zA-Z0-9_-]+)(?:@(?P<version>.+))?$")


def parse_dep(dep_str: str) -> tuple[str, str | None]:
    """Parse 'module-name@version' into (name, version_constraint).

    Version constraints are recorded but not evaluated — semantic versioning
    enforcement is a future enhancement.
    """
    m = _DEP_RE.match(dep_str.strip())
    if not m:
        raise ValueError(
            f"Invalid dependency format: {dep_str!r}. Expected 'name' or 'name@version'."
        )
    return m.group("name"), m.group("version")


def check_dependencies(
    depends_on: list[str],
    installed_names: set[str],
) -> list[str]:
    """Return names of dependencies declared in depends_on that are not installed."""
    unmet: list[str] = []
    for dep in depends_on:
        name, _version = parse_dep(dep)
        if name not in installed_names:
            unmet.append(name)
    return unmet
