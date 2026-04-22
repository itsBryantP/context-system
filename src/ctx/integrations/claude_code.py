"""Claude Code (and cross-framework) integration — symlink management and file patching."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Files a module may carry for each supported tool
_CROSS_TOOL_FILES: dict[str, str] = {
    "cursor": ".cursorrules",
    "copilot": "COPILOT.md",
    "continue": ".continuerules",
    "bob": "BOB.md",
}

# Heuristics for auto-detecting which tools are active in a project
_TOOL_INDICATORS: dict[str, list[str]] = {
    "cursor": [".cursor", ".cursorrules"],
    "copilot": [".github"],
    "continue": [".continuerules"],
    "bob": [".bob", "BOB.md"],
}


@dataclass
class InstallResult:
    module_name: str
    skills: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    claude_md_patched: bool = False
    tool_files: list[str] = field(default_factory=list)  # e.g. [".cursorrules"]


@dataclass
class RemoveResult:
    module_name: str
    skills_removed: list[str] = field(default_factory=list)
    rules_removed: list[str] = field(default_factory=list)
    claude_md_patched: bool = False
    tool_files_removed: list[str] = field(default_factory=list)


# ── Install ───────────────────────────────────────────────────────────────────


def install_module(
    module_path: Path,
    project_root: Path,
    tools: list[str] | None = None,
) -> InstallResult:
    """Wire a module's skills, rules, CLAUDE.md, and cross-framework files into a project.

    Args:
        tools: explicit list of tool names to install for, e.g. ["claude", "cursor"].
               Pass None to auto-detect from the project structure.
               Always includes "claude" unless explicitly excluded.
    """
    module_path = module_path.resolve()
    project_root = project_root.resolve()

    from ctx.module import load_module
    mod = load_module(module_path)
    result = InstallResult(module_name=mod.name)

    active_tools = _resolve_tools(tools, project_root)

    if "claude" in active_tools:
        _install_skills(module_path, project_root, result)
        _install_rules(module_path, project_root, result)
        _patch_claude_md_add(module_path, project_root, result)

    if "bob" in active_tools:
        _install_bob_integration(module_path, project_root, result)

    for tool in active_tools:
        if tool in _CROSS_TOOL_FILES:
            _install_tool_file(tool, module_path, project_root, result)

    return result


def _resolve_tools(tools: list[str] | None, project_root: Path) -> set[str]:
    """Return the set of tools to install for."""
    if tools:
        return set(tools)
    # Auto-detect: always claude; others based on project indicators
    active = {"claude"}
    for tool, indicators in _TOOL_INDICATORS.items():
        if any((project_root / ind).exists() for ind in indicators):
            active.add(tool)
    return active


def _install_tool_file(
    tool: str, module_path: Path, project_root: Path, result: InstallResult
) -> None:
    filename = _CROSS_TOOL_FILES[tool]
    src = module_path / filename
    if not src.exists():
        return
    link = project_root / filename
    _create_symlink(src, link)
    result.tool_files.append(filename)


def _install_bob_integration(
    module_path: Path, project_root: Path, result: InstallResult
) -> None:
    """Install Bob Shell-specific files (modes, tools, servers, BOB.md)."""
    bob_dir = project_root / ".bob"
    
    # Install modes if present
    modes_src = module_path / "bob" / "modes"
    if modes_src.is_dir():
        modes_dst = bob_dir / "modes"
        modes_dst.mkdir(parents=True, exist_ok=True)
        for mode_file in sorted(modes_src.glob("*.yaml")):
            link = modes_dst / mode_file.name
            _create_symlink(mode_file, link)
            result.tool_files.append(f".bob/modes/{mode_file.name}")
    
    # Install tools if present
    tools_src = module_path / "bob" / "tools"
    if tools_src.is_dir():
        tools_dst = bob_dir / "tools"
        tools_dst.mkdir(parents=True, exist_ok=True)
        for tool_file in sorted(tools_src.glob("*.yaml")):
            link = tools_dst / tool_file.name
            _create_symlink(tool_file, link)
            result.tool_files.append(f".bob/tools/{tool_file.name}")
    
    # Install MCP servers if present
    servers_src = module_path / "bob" / "servers"
    if servers_src.is_dir():
        servers_dst = bob_dir / "servers"
        servers_dst.mkdir(parents=True, exist_ok=True)
        for server_file in sorted(servers_src.glob("*.json")):
            link = servers_dst / server_file.name
            _create_symlink(server_file, link)
            result.tool_files.append(f".bob/servers/{server_file.name}")


def _remove_bob_integration(
    module_path: Path, project_root: Path, result: RemoveResult
) -> None:
    """Remove Bob Shell-specific files."""
    bob_dir = project_root / ".bob"
    
    # Remove modes
    modes_src = module_path / "bob" / "modes"
    if modes_src.is_dir():
        modes_dst = bob_dir / "modes"
        for mode_file in sorted(modes_src.glob("*.yaml")):
            link = modes_dst / mode_file.name
            if link.is_symlink() and link.resolve() == mode_file.resolve():
                link.unlink()
                result.tool_files_removed.append(f".bob/modes/{mode_file.name}")
    
    # Remove tools
    tools_src = module_path / "bob" / "tools"
    if tools_src.is_dir():
        tools_dst = bob_dir / "tools"
        for tool_file in sorted(tools_src.glob("*.yaml")):
            link = tools_dst / tool_file.name
            if link.is_symlink() and link.resolve() == tool_file.resolve():
                link.unlink()
                result.tool_files_removed.append(f".bob/tools/{tool_file.name}")
    
    # Remove MCP servers
    servers_src = module_path / "bob" / "servers"
    if servers_src.is_dir():
        servers_dst = bob_dir / "servers"
        for server_file in sorted(servers_src.glob("*.json")):
            link = servers_dst / server_file.name
            if link.is_symlink() and link.resolve() == server_file.resolve():
                link.unlink()
                result.tool_files_removed.append(f".bob/servers/{server_file.name}")


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
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return
        link.unlink()
    elif link.exists():
        raise FileExistsError(
            f"{link} exists and is not a symlink. Remove it manually before installing."
        )
    os.symlink(target, link)


def _patch_claude_md_add(
    module_path: Path, project_root: Path, result: InstallResult
) -> None:
    module_claude_md = module_path / "CLAUDE.md"
    if not module_claude_md.exists():
        return
    project_claude_md = project_root / "CLAUDE.md"
    import_line = f"@{module_claude_md}"
    if project_claude_md.exists():
        existing = project_claude_md.read_text()
        if import_line in existing:
            return
        updated = existing.rstrip("\n") + f"\n{import_line}\n"
    else:
        updated = f"{import_line}\n"
    project_claude_md.write_text(updated)
    result.claude_md_patched = True


# ── Remove ────────────────────────────────────────────────────────────────────


def remove_module(
    module_path: Path,
    project_root: Path,
    tools: list[str] | None = None,
) -> RemoveResult:
    """Reverse all changes made by install_module."""
    module_path = module_path.resolve()
    project_root = project_root.resolve()

    from ctx.module import load_module
    mod = load_module(module_path)
    result = RemoveResult(module_name=mod.name)

    active_tools = _resolve_tools(tools, project_root)

    if "claude" in active_tools:
        _remove_skills(module_path, project_root, result)
        _remove_rules(module_path, project_root, result)
        _patch_claude_md_remove(module_path, project_root, result)

    if "bob" in active_tools:
        _remove_bob_integration(module_path, project_root, result)

    for tool in active_tools:
        if tool in _CROSS_TOOL_FILES:
            _remove_tool_file(tool, module_path, project_root, result)

    return result


def _remove_tool_file(
    tool: str, module_path: Path, project_root: Path, result: RemoveResult
) -> None:
    filename = _CROSS_TOOL_FILES[tool]
    src = module_path / filename
    link = project_root / filename
    if link.is_symlink() and link.resolve() == src.resolve():
        link.unlink()
        result.tool_files_removed.append(filename)


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
    module_path: Path, project_root: Path, result: RemoveResult
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
