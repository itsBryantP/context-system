"""Tests for Claude Code integration — symlink management and CLAUDE.md patching."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ctx.integrations.claude_code import install_module, remove_module


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_module(
    base: Path,
    name: str = "test-mod",
    *,
    with_skills: list[str] | None = None,
    with_rules: list[str] | None = None,
    with_claude_md: bool = False,
) -> Path:
    """Scaffold a minimal module directory for testing."""
    mod = base / name
    (mod / "content").mkdir(parents=True)
    (mod / "content" / "overview.md").write_text(f"# {name}\n\nContent.\n")
    (mod / "module.yaml").write_text(
        yaml.dump({"name": name, "version": "1.0.0", "description": f"{name} module"})
    )

    if with_skills:
        for skill in with_skills:
            skill_dir = mod / "skills" / skill
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# {skill}\n")

    if with_rules:
        rules_dir = mod / "rules"
        rules_dir.mkdir(parents=True)
        for rule in with_rules:
            (rules_dir / f"{rule}.md").write_text(f"# {rule} rules\n")

    if with_claude_md:
        (mod / "CLAUDE.md").write_text(f"# {name} context\n\nSome guidance.\n")

    return mod


def make_project(base: Path) -> Path:
    project = base / "project"
    project.mkdir()
    return project


# ── install_module ────────────────────────────────────────────────────────────


class TestInstallModule:
    def test_no_skills_or_rules(self, tmp_path):
        mod = make_module(tmp_path / "mods")
        project = make_project(tmp_path)

        result = install_module(mod, project)

        assert result.module_name == "test-mod"
        assert result.skills == []
        assert result.rules == []
        assert result.claude_md_patched is False

    def test_installs_skill_symlinks(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_skills=["review-api", "lint"])
        project = make_project(tmp_path)

        result = install_module(mod, project)

        assert sorted(result.skills) == ["lint", "review-api"]
        assert (project / ".claude" / "skills" / "review-api").is_symlink()
        assert (project / ".claude" / "skills" / "lint").is_symlink()
        assert (project / ".claude" / "skills" / "review-api").resolve() == (mod / "skills" / "review-api").resolve()

    def test_installs_rule_symlinks(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_rules=["api-validation", "naming"])
        project = make_project(tmp_path)

        result = install_module(mod, project)

        assert sorted(result.rules) == ["api-validation.md", "naming.md"]
        assert (project / ".claude" / "rules" / "api-validation.md").is_symlink()

    def test_patches_claude_md(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_claude_md=True)
        project = make_project(tmp_path)

        result = install_module(mod, project)

        assert result.claude_md_patched is True
        project_claude = (project / "CLAUDE.md").read_text()
        assert f"@{mod / 'CLAUDE.md'}" in project_claude

    def test_appends_to_existing_claude_md(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_claude_md=True)
        project = make_project(tmp_path)
        (project / "CLAUDE.md").write_text("# My Project\n\nExisting content.\n")

        install_module(mod, project)

        content = (project / "CLAUDE.md").read_text()
        assert "# My Project" in content
        assert f"@{mod / 'CLAUDE.md'}" in content

    def test_idempotent_second_install(self, tmp_path):
        mod = make_module(
            tmp_path / "mods",
            with_skills=["skill-a"],
            with_rules=["rule-a"],
            with_claude_md=True,
        )
        project = make_project(tmp_path)

        install_module(mod, project)
        install_module(mod, project)  # second call — should not error or duplicate

        content = (project / "CLAUDE.md").read_text()
        import_line = f"@{mod / 'CLAUDE.md'}"
        assert content.count(import_line) == 1

    def test_no_claude_md_patch_when_module_has_none(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_claude_md=False)
        project = make_project(tmp_path)

        result = install_module(mod, project)

        assert result.claude_md_patched is False
        assert not (project / "CLAUDE.md").exists()

    def test_raises_on_non_symlink_conflict(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_skills=["skill-a"])
        project = make_project(tmp_path)
        skills_dst = project / ".claude" / "skills"
        skills_dst.mkdir(parents=True)
        (skills_dst / "skill-a").mkdir()  # real directory, not symlink

        with pytest.raises(FileExistsError, match="not a symlink"):
            install_module(mod, project)


# ── remove_module ─────────────────────────────────────────────────────────────


class TestRemoveModule:
    def test_removes_skill_symlinks(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_skills=["review-api"])
        project = make_project(tmp_path)
        install_module(mod, project)

        result = remove_module(mod, project)

        assert "review-api" in result.skills_removed
        assert not (project / ".claude" / "skills" / "review-api").exists()

    def test_removes_rule_symlinks(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_rules=["api-validation"])
        project = make_project(tmp_path)
        install_module(mod, project)

        result = remove_module(mod, project)

        assert "api-validation.md" in result.rules_removed
        assert not (project / ".claude" / "rules" / "api-validation.md").exists()

    def test_removes_claude_md_import(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_claude_md=True)
        project = make_project(tmp_path)
        (project / "CLAUDE.md").write_text("# Project\n\nContent.\n")
        install_module(mod, project)

        result = remove_module(mod, project)

        assert result.claude_md_patched is True
        content = (project / "CLAUDE.md").read_text()
        assert f"@{mod / 'CLAUDE.md'}" not in content
        assert "# Project" in content  # rest of file preserved

    def test_remove_is_idempotent(self, tmp_path):
        mod = make_module(tmp_path / "mods", with_skills=["skill-a"], with_claude_md=True)
        project = make_project(tmp_path)
        install_module(mod, project)
        remove_module(mod, project)
        result = remove_module(mod, project)  # second remove — should not error

        assert result.skills_removed == []
        assert result.claude_md_patched is False

    def test_does_not_remove_unrelated_symlinks(self, tmp_path):
        mod_a = make_module(tmp_path / "mods", "mod-a", with_skills=["shared-skill"])
        mod_b = make_module(tmp_path / "mods", "mod-b", with_skills=["other-skill"])
        project = make_project(tmp_path)
        install_module(mod_a, project)
        install_module(mod_b, project)

        remove_module(mod_a, project)

        assert not (project / ".claude" / "skills" / "shared-skill").exists()
        assert (project / ".claude" / "skills" / "other-skill").is_symlink()
