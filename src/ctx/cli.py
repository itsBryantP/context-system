"""CLI: init, create, build, chunks, list, extract, sync, add, remove."""

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
@click.argument("source")
@click.option("--into", "-i", "module_path", required=True, type=click.Path(exists=True), help="Target module directory")
@click.option("--type", "-t", "source_type", type=click.Choice(["pdf", "pptx", "markdown", "url"]), help="Force source type (auto-detected if omitted)")
def extract(source, module_path, source_type):
    """Extract a source file or URL into a module's content/ directory."""
    from ctx.extractors import get_extractor
    from ctx.schema import Source, SourceType

    mod_path = Path(module_path).resolve()

    if source_type:
        stype = SourceType(source_type)
    elif source.startswith(("http://", "https://")):
        stype = SourceType.URL
    elif source.lower().endswith(".pdf"):
        stype = SourceType.PDF
    elif source.lower().endswith((".pptx", ".ppt")):
        stype = SourceType.PPTX
    else:
        stype = SourceType.MARKDOWN

    src = Source(
        type=stype,
        path=source if stype != SourceType.URL else None,
        url=source if stype == SourceType.URL else None,
    )

    extractor = get_extractor(src)
    created = extractor.extract(src, mod_path / "content")

    for path in created:
        click.echo(f"  Extracted → {path.relative_to(mod_path)}")


@cli.command()
@click.argument("module_path", type=click.Path(exists=True))
def sync(module_path):
    """Re-extract all sources declared in module.yaml into content/."""
    from ctx.extractors import get_extractor

    path = Path(module_path).resolve()
    mod = load_module(path)

    if not mod.sources:
        raise click.ClickException(f"No sources declared in {mod.name}/module.yaml")

    output_dir = path / "content"
    total = 0

    for source in mod.sources:
        extractor = get_extractor(source)
        created = extractor.extract(source, output_dir)
        for f in created:
            click.echo(f"  [{source.type.value}] → {f.name}")
            total += 1

    click.echo(f"Synced {total} file(s) for {mod.name}")


@cli.command()
@click.argument("module_path", type=click.Path(exists=True))
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
def add(module_path, project):
    """Install a module's skills, rules, and CLAUDE.md into this project."""
    from ctx.integrations.claude_code import install_module

    mod_path = Path(module_path).resolve()
    project_root = Path(project).resolve()

    issues = validate_module(mod_path)
    if issues:
        raise click.ClickException(f"Invalid module: {'; '.join(issues)}")

    result = install_module(mod_path, project_root)

    # Record in .context/config.yaml
    config = load_config(project_root)
    ref_path = str(mod_path)
    if not any(m.path == ref_path for m in config.modules):
        config.modules.append(ModuleRef(path=ref_path))
        save_config(project_root, config)

    for name in result.skills:
        click.echo(f"  skill   → .claude/skills/{name}")
    for name in result.rules:
        click.echo(f"  rule    → .claude/rules/{name}")
    if result.claude_md_patched:
        click.echo(f"  CLAUDE.md patched with @import")

    click.echo(f"Added {result.module_name}")


@cli.command()
@click.argument("module_name")
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
def remove(module_name, project):
    """Remove a module's skills, rules, and CLAUDE.md import from this project."""
    from ctx.integrations.claude_code import remove_module

    project_root = Path(project).resolve()
    config = load_config(project_root)

    ref = next((m for m in config.modules if Path(m.path).name == module_name or
                load_module(resolve_module_path(m.path, project_root)).name == module_name
                ), None)
    if ref is None:
        raise click.ClickException(f"Module '{module_name}' not found in .context/config.yaml")

    mod_path = resolve_module_path(ref.path, project_root)
    result = remove_module(mod_path, project_root)

    # Remove from config
    config.modules = [m for m in config.modules if m.path != ref.path]
    save_config(project_root, config)

    for name in result.skills_removed:
        click.echo(f"  removed skill   .claude/skills/{name}")
    for name in result.rules_removed:
        click.echo(f"  removed rule    .claude/rules/{name}")
    if result.claude_md_patched:
        click.echo(f"  CLAUDE.md import removed")

    click.echo(f"Removed {result.module_name}")


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
