"""Claude Code integration — symlink management and CLAUDE.md patching."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InstallResult:
    module_name: str
    skills: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    claude_md_patched: bool = False


@dataclass
class RemoveResult:
    module_name: str
    skills_removed: list[str] = field(default_factory=list)
    rules_removed: list[str] = field(default_factory=list)
    claude_md_patched: bool = False


# ── Install ───────────────────────────────────────────────────────────────────


def install_module(
    module_path: Path,
    project_root: Path,
) -> InstallResult:
    """Wire a module's skills, rules, and CLAUDE.md into the project.

    Creates symlinks under .claude/ and patches the project's CLAUDE.md.
    Idempotent: existing symlinks that already point to the same target are kept.
    """
    module_path = module_path.resolve()
    project_root = project_root.resolve()

    from ctx.module import load_module  # avoid circular at module level
    mod = load_module(module_path)
    result = InstallResult(module_name=mod.name)

    _install_skills(module_path, project_root, result)
    _install_rules(module_path, project_root, result)
    _patch_claude_md_add(module_path, project_root, mod.name, result)

    return result


def _install_skills(module_path: Path, project_root: Path, result: InstallResult) -> None:
    skills_src = module_path / "skills"
    if not skills_src.is_dir():
        return

    skills_dst = project_root / ".claude" / "skills"
    skills_dst.mkdir(parents=True, exist_ok=True)

    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir():
            continue
        link = skills_dst / skill_dir.name
        _create_symlink(skill_dir, link)
        result.skills.append(skill_dir.name)


def _install_rules(module_path: Path, project_root: Path, result: InstallResult) -> None:
    rules_src = module_path / "rules"
    if not rules_src.is_dir():
        return

    rules_dst = project_root / ".claude" / "rules"
    rules_dst.mkdir(parents=True, exist_ok=True)

    for rule_file in sorted(rules_src.glob("*.md")):
        link = rules_dst / rule_file.name
        _create_symlink(rule_file, link)
        result.rules.append(rule_file.name)


def _create_symlink(target: Path, link: Path) -> None:
    """Create a symlink at link → target. Replaces an existing link if target differs."""
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return  # already correct
        link.unlink()
    elif link.exists():
        raise FileExistsError(
            f"{link} exists and is not a symlink. Remove it manually before installing."
        )
    os.symlink(target, link)


def _patch_claude_md_add(
    module_path: Path,
    project_root: Path,
    module_name: str,
    result: InstallResult,
) -> None:
    module_claude_md = module_path / "CLAUDE.md"
    if not module_claude_md.exists():
        return

    project_claude_md = project_root / "CLAUDE.md"
    import_line = f"@{module_claude_md}"

    if project_claude_md.exists():
        existing = project_claude_md.read_text()
        if import_line in existing:
            return  # already imported
        updated = existing.rstrip("\n") + f"\n{import_line}\n"
    else:
        updated = f"{import_line}\n"

    project_claude_md.write_text(updated)
    result.claude_md_patched = True


# ── Remove ────────────────────────────────────────────────────────────────────


def remove_module(
    module_path: Path,
    project_root: Path,
) -> RemoveResult:
    """Reverse all symlinks and CLAUDE.md changes made by install_module."""
    module_path = module_path.resolve()
    project_root = project_root.resolve()

    from ctx.module import load_module
    mod = load_module(module_path)
    result = RemoveResult(module_name=mod.name)

    _remove_skills(module_path, project_root, result)
    _remove_rules(module_path, project_root, result)
    _patch_claude_md_remove(module_path, project_root, result)

    return result


def _remove_skills(module_path: Path, project_root: Path, result: RemoveResult) -> None:
    skills_src = module_path / "skills"
    if not skills_src.is_dir():
        return

    skills_dst = project_root / ".claude" / "skills"
    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir():
            continue
        link = skills_dst / skill_dir.name
        if link.is_symlink() and link.resolve() == skill_dir.resolve():
            link.unlink()
            result.skills_removed.append(skill_dir.name)


def _remove_rules(module_path: Path, project_root: Path, result: RemoveResult) -> None:
    rules_src = module_path / "rules"
    if not rules_src.is_dir():
        return

    rules_dst = project_root / ".claude" / "rules"
    for rule_file in sorted(rules_src.glob("*.md")):
        link = rules_dst / rule_file.name
        if link.is_symlink() and link.resolve() == rule_file.resolve():
            link.unlink()
            result.rules_removed.append(rule_file.name)


def _patch_claude_md_remove(
    module_path: Path,
    project_root: Path,
    result: RemoveResult,
) -> None:
    module_claude_md = module_path / "CLAUDE.md"
    project_claude_md = project_root / "CLAUDE.md"

    if not project_claude_md.exists():
        return

    import_line = f"@{module_claude_md}"
    existing = project_claude_md.read_text()

    if import_line not in existing:
        return

    updated = "\n".join(
        line for line in existing.splitlines() if line.strip() != import_line
    ).rstrip("\n") + "\n"

    project_claude_md.write_text(updated)
    result.claude_md_patched = True
