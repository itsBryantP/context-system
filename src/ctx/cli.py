"""CLI: init, create, build, chunks, list."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import yaml

from ctx.config import init_project, load_config, save_config
from ctx.module import get_content_files, load_module, resolve_module_path, validate_module
from ctx.schema import ChunkingStrategy, ModuleConfig, ModuleRef
from ctx.chunker.heading import HeadingChunker
from ctx.chunker.fixed import FixedChunker
from ctx.integrations.jsonl import chunks_to_jsonl, write_jsonl


def _get_chunker(strategy: ChunkingStrategy):
    if strategy == ChunkingStrategy.HEADING:
        return HeadingChunker()
    elif strategy == ChunkingStrategy.FIXED:
        return FixedChunker()
    else:
        raise click.ClickException(f"Strategy '{strategy.value}' not yet implemented")


def _build_module(module_path: Path, config=None):
    """Build chunks for a single module. Returns list of Chunks."""
    mod = load_module(module_path)
    chunker = _get_chunker(mod.chunking.strategy)
    all_chunks = []

    for content_file in get_content_files(module_path):
        rel_path = str(content_file.relative_to(module_path))
        content = content_file.read_text()

        chunks = chunker.chunk(
            content,
            module_name=mod.name,
            source_file=rel_path,
            tags=mod.tags,
            version=mod.version,
            max_tokens=mod.chunking.max_tokens,
            overlap_tokens=mod.chunking.overlap_tokens,
            heading_level=mod.chunking.heading_level,
        )
        all_chunks.extend(chunks)

    return all_chunks, mod


@click.group()
def cli():
    """ctx — Context module system for RAG and AI coding tools."""
    pass


@cli.command()
@click.argument("path", default=".", type=click.Path())
def init(path):
    """Initialize a project with .context/config.yaml."""
    project_root = Path(path).resolve()
    config = init_project(project_root)
    click.echo(f"Initialized ctx project at {project_root / '.context'}")


@cli.command()
@click.argument("name")
@click.option("--path", "-p", default=".", type=click.Path(), help="Parent directory")
def create(name, path):
    """Create a new context module scaffold."""
    module_dir = Path(path).resolve() / name
    if module_dir.exists():
        raise click.ClickException(f"Directory already exists: {module_dir}")

    module_dir.mkdir(parents=True)
    (module_dir / "content").mkdir()

    mod = ModuleConfig(name=name, description=f"{name} context module")
    yaml_data = mod.model_dump(mode="json", exclude_defaults=True)
    (module_dir / "module.yaml").write_text(
        yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
    )

    # Starter content file
    (module_dir / "content" / "overview.md").write_text(
        f"# {name}\n\nAdd your content here.\n"
    )

    click.echo(f"Created module: {module_dir}")
    click.echo(f"  module.yaml")
    click.echo(f"  content/overview.md")


@cli.command()
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
def build(project):
    """Build JSONL chunks for all configured modules."""
    project_root = Path(project).resolve()
    config = load_config(project_root)

    if not config.modules:
        raise click.ClickException(
            "No modules configured. Add modules to .context/config.yaml or use 'ctx build <path>'"
        )

    chunks_dir = project_root / config.output.chunks_dir
    total = 0

    for mod_ref in config.modules:
        module_path = resolve_module_path(mod_ref.path, project_root)
        issues = validate_module(module_path)
        if issues:
            click.echo(f"Skipping {mod_ref.path}: {'; '.join(issues)}", err=True)
            continue

        chunks, mod = _build_module(module_path)
        if chunks:
            out = write_jsonl(chunks, chunks_dir / f"{mod.name}.jsonl")
            click.echo(f"  {mod.name}: {len(chunks)} chunks → {out}")
            total += len(chunks)

    click.echo(f"Build complete: {total} total chunks")


@cli.command()
@click.argument("module_path", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", default="jsonl", type=click.Choice(["jsonl", "text"]))
def chunks(module_path, fmt):
    """Output chunks for a module to stdout."""
    path = Path(module_path).resolve()
    all_chunks, mod = _build_module(path)

    if fmt == "jsonl":
        output = chunks_to_jsonl(all_chunks)
        click.echo(output, nl=False)
    else:
        for chunk in all_chunks:
            click.echo(f"--- [{chunk.id}] ({chunk.metadata.get('token_count', '?')} tokens) ---")
            click.echo(chunk.content)
            click.echo()


@cli.command(name="list")
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
def list_modules(project):
    """List configured modules."""
    project_root = Path(project).resolve()
    config = load_config(project_root)

    if not config.modules:
        click.echo("No modules configured.")
        return

    for mod_ref in config.modules:
        module_path = resolve_module_path(mod_ref.path, project_root)
        try:
            mod = load_module(module_path)
            files = get_content_files(module_path)
            click.echo(f"  {mod.name} v{mod.version} — {mod.description} ({len(files)} files)")
        except Exception as e:
            click.echo(f"  {mod_ref.path} — ERROR: {e}")


@cli.command()
@click.argument("module_path", type=click.Path(exists=True))
def validate(module_path):
    """Validate a module directory."""
    path = Path(module_path).resolve()
    issues = validate_module(path)
    if issues:
        for issue in issues:
            click.echo(f"  ✗ {issue}", err=True)
        sys.exit(1)
    else:
        mod = load_module(path)
        click.echo(f"  ✓ {mod.name} v{mod.version} is valid")
