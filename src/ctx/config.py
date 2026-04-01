"""Load and save .context/config.yaml project configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from ctx.schema import ProjectConfig

CONFIG_DIR = ".context"
CONFIG_FILE = "config.yaml"


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_DIR / CONFIG_FILE


def load_config(project_root: Path) -> ProjectConfig:
    """Load project config from .context/config.yaml. Returns defaults if missing."""
    path = config_path(project_root)
    if not path.exists():
        return ProjectConfig()
    data = yaml.safe_load(path.read_text()) or {}
    return ProjectConfig.model_validate(data)


def save_config(project_root: Path, config: ProjectConfig) -> Path:
    """Save project config to .context/config.yaml. Creates directories as needed."""
    path = config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


def init_project(project_root: Path) -> ProjectConfig:
    """Initialize a new project with default config. Returns the config."""
    path = config_path(project_root)
    if path.exists():
        return load_config(project_root)
    config = ProjectConfig()
    save_config(project_root, config)
    # Create chunks output directory
    chunks_dir = project_root / config.output.chunks_dir
    chunks_dir.mkdir(parents=True, exist_ok=True)
    return config
