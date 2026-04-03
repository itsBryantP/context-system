"""Load, validate, and resolve modules from local paths or git URLs."""

from __future__ import annotations

from pathlib import Path

import yaml

from ctx.schema import ModuleConfig, ModuleRef


def load_module(module_path: Path) -> ModuleConfig:
    """Load and validate a module from its directory."""
    module_path = module_path.resolve()
    yaml_path = module_path / "module.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No module.yaml found in {module_path}")
    data = yaml.safe_load(yaml_path.read_text()) or {}
    return ModuleConfig.model_validate(data)


def get_content_files(module_path: Path) -> list[Path]:
    """Return all markdown files in a module's content/ directory, sorted."""
    content_dir = module_path / "content"
    if not content_dir.exists():
        return []
    return sorted(content_dir.rglob("*.md"))


def resolve_module_path(path_str: str, project_root: Path) -> Path:
    """Resolve a local module path (absolute or relative to project root)."""
    path = Path(path_str).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def resolve_module_ref(ref: ModuleRef, project_root: Path) -> Path:
    """Resolve a ModuleRef to a local path, cloning from git if necessary."""
    if ref.git:
        from ctx.git import resolve_git_module
        return resolve_git_module(ref.git)
    return resolve_module_path(ref.path, project_root)  # type: ignore[arg-type]


def validate_module(module_path: Path) -> list[str]:
    """Validate a module directory. Returns list of issues (empty = valid)."""
    issues = []
    module_path = module_path.resolve()

    if not module_path.is_dir():
        issues.append(f"Module path is not a directory: {module_path}")
        return issues

    yaml_path = module_path / "module.yaml"
    if not yaml_path.exists():
        issues.append("Missing module.yaml")
        return issues

    try:
        load_module(module_path)
    except Exception as e:
        issues.append(f"Invalid module.yaml: {e}")
        return issues

    content_dir = module_path / "content"
    if not content_dir.exists():
        issues.append("Missing content/ directory")
    elif not list(content_dir.rglob("*.md")):
        issues.append("No markdown files in content/")

    return issues
