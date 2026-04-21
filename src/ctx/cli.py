"""CLI: init, create, build, chunks, list, extract, sync, add, remove, validate."""

from __future__ import annotations

import sys
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError

import click
import yaml

from ctx.config import init_project, load_config, save_config
from ctx.module import get_content_files, load_module, resolve_module_path, resolve_module_ref, validate_module
from ctx.schema import ChunkingStrategy, ModuleConfig, ModuleRef
from ctx.chunker.heading import HeadingChunker
from ctx.chunker.fixed import FixedChunker
from ctx.integrations.jsonl import chunks_to_jsonl, write_jsonl


def _get_chunker(strategy: ChunkingStrategy):
    if strategy == ChunkingStrategy.HEADING:
        return HeadingChunker()
    elif strategy == ChunkingStrategy.FIXED:
        return FixedChunker()
    elif strategy == ChunkingStrategy.DEFINITION:
        from ctx.chunker.definition import DefinitionChunker
        return DefinitionChunker()
    else:
        raise click.ClickException(f"Unknown chunking strategy: {strategy.value!r}")


def _build_module(
    module_path: Path,
    source_hash: str | None = None,
    contextualize_cache: Path | None = None,
):
    """Build chunks for a single module. Returns (chunks, mod)."""
    mod = load_module(module_path)
    chunker = _get_chunker(mod.chunking.strategy)
    all_chunks = []

    for content_file in get_content_files(module_path):
        rel_path = str(content_file.relative_to(module_path))
        text = content_file.read_text()
        chunks = chunker.chunk(
            text,
            module_name=mod.name,
            source_file=rel_path,
            tags=mod.tags,
            version=mod.version,
            max_tokens=mod.chunking.max_tokens,
            overlap_tokens=mod.chunking.overlap_tokens,
            heading_level=mod.chunking.heading_level,
        )

        if mod.chunking.contextualize and chunks:
            try:
                from ctx.chunker.contextualize import (
                    ContextualizeError,
                    contextualize_chunks,
                )
            except ImportError as e:
                raise click.ClickException(str(e)) from e
            try:
                chunks = contextualize_chunks(
                    chunks,
                    text,
                    model=mod.chunking.contextualize_model,
                    cache_path=contextualize_cache,
                )
            except ContextualizeError as e:
                raise click.ClickException(str(e)) from e

        if source_hash:
            for chunk in chunks:
                chunk.metadata["source_hash"] = source_hash
        all_chunks.extend(chunks)

    return all_chunks, mod


def _get_version():
    """Get the package version."""
    try:
        return version("ctx-modules")
    except PackageNotFoundError:
        return "unknown"


@click.group()
@click.version_option(version=_get_version(), prog_name="ctx")
def cli():
    """ctx — Context module system for RAG and AI coding tools."""
    pass


@cli.command()
@click.argument("path", default=".", type=click.Path())
def init(path):
    """Initialize a project with .context/config.yaml."""
    project_root = Path(path).resolve()
    init_project(project_root)
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
    (module_dir / "content" / "overview.md").write_text(
        f"# {name}\n\nAdd your content here.\n"
    )

    click.echo(f"Created module: {module_dir}")
    click.echo("  module.yaml")
    click.echo("  content/overview.md")


@cli.command()
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
@click.option("--force", is_flag=True, help="Rebuild even if content is unchanged")
def build(project, force):
    """Build JSONL chunks for all configured modules."""
    from ctx.deps import check_dependencies
    from ctx.freshness import compute_module_hash, is_fresh, load_build_meta, record_build

    project_root = Path(project).resolve()
    config = load_config(project_root)

    if not config.modules:
        raise click.ClickException(
            "No modules configured. Add modules to .context/config.yaml or run 'ctx add'."
        )

    installed_names = set()
    for ref in config.modules:
        try:
            mp = resolve_module_ref(ref, project_root)
            installed_names.add(load_module(mp).name)
        except Exception:
            pass

    meta = load_build_meta(project_root)
    chunks_dir = project_root / config.output.chunks_dir
    total = 0

    for mod_ref in config.modules:
        try:
            module_path = resolve_module_ref(mod_ref, project_root)
        except Exception as e:
            click.echo(f"  Skipping {mod_ref.path or mod_ref.git}: {e}", err=True)
            continue

        issues = validate_module(module_path)
        if issues:
            click.echo(f"  Skipping {module_path.name}: {'; '.join(issues)}", err=True)
            continue

        mod = load_module(module_path)

        # Dependency check — warn but don't abort
        unmet = check_dependencies(mod.depends_on, installed_names)
        for dep in unmet:
            click.echo(f"  Warning: {mod.name} depends on '{dep}' which is not installed", err=True)

        # Freshness check
        source_hash = compute_module_hash(module_path)
        if not force and is_fresh(mod.name, source_hash, meta):
            click.echo(f"  {mod.name}: up to date (skipped)")
            continue

        cache_path = project_root / ".context" / ".contextualize-cache.json"
        chunks, mod = _build_module(
            module_path,
            source_hash=source_hash,
            contextualize_cache=cache_path,
        )
        if chunks:
            out = write_jsonl(chunks, chunks_dir / f"{mod.name}.jsonl")
            click.echo(f"  {mod.name}: {len(chunks)} chunks → {out}")
            record_build(project_root, mod.name, source_hash, len(chunks))
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
        click.echo(chunks_to_jsonl(all_chunks), nl=False)
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
        try:
            module_path = resolve_module_ref(mod_ref, project_root)
            mod = load_module(module_path)
            files = get_content_files(module_path)
            source = mod_ref.git or mod_ref.path or ""
            click.echo(f"  {mod.name} v{mod.version} — {mod.description} ({len(files)} files)  [{source}]")
        except Exception as e:
            click.echo(f"  {mod_ref.path or mod_ref.git} — ERROR: {e}")


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
    elif source.lower().endswith(".pptx"):
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
@click.option("--tool", "tools", multiple=True,
              type=click.Choice(["claude", "cursor", "copilot", "continue"]),
              help="Tool(s) to install for. Repeatable. Defaults to auto-detect.")
def add(module_path, project, tools):
    """Install a module's skills, rules, CLAUDE.md, and cross-framework files."""
    from ctx.integrations.claude_code import install_module

    mod_path = Path(module_path).resolve()
    project_root = Path(project).resolve()

    issues = validate_module(mod_path)
    if issues:
        raise click.ClickException(f"Invalid module: {'; '.join(issues)}")

    result = install_module(mod_path, project_root, tools=list(tools) or None)

    config = load_config(project_root)
    ref_path = str(mod_path)
    if not any(m.path == ref_path for m in config.modules):
        config.modules.append(ModuleRef(path=ref_path))
        save_config(project_root, config)

    for name in result.skills:
        click.echo(f"  skill      → .claude/skills/{name}")
    for name in result.rules:
        click.echo(f"  rule       → .claude/rules/{name}")
    if result.claude_md_patched:
        click.echo("  CLAUDE.md  → @import added")
    for fname in result.tool_files:
        click.echo(f"  tool file  → {fname}")

    click.echo(f"Added {result.module_name}")


@cli.command()
@click.argument("module_name")
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
def remove(module_name, project):
    """Remove a module's skills, rules, CLAUDE.md import, and tool files."""
    from ctx.integrations.claude_code import remove_module

    project_root = Path(project).resolve()
    config = load_config(project_root)

    ref = next(
        (m for m in config.modules
         if _module_name_matches(m, module_name, project_root)),
        None,
    )
    if ref is None:
        raise click.ClickException(f"Module '{module_name}' not found in .context/config.yaml")

    mod_path = resolve_module_ref(ref, project_root)
    result = remove_module(mod_path, project_root)

    config.modules = [m for m in config.modules if m is not ref]
    save_config(project_root, config)

    for name in result.skills_removed:
        click.echo(f"  removed skill      .claude/skills/{name}")
    for name in result.rules_removed:
        click.echo(f"  removed rule       .claude/rules/{name}")
    if result.claude_md_patched:
        click.echo("  removed CLAUDE.md  @import")
    for fname in result.tool_files_removed:
        click.echo(f"  removed tool file  {fname}")

    click.echo(f"Removed {result.module_name}")


def _module_name_matches(ref: ModuleRef, target_name: str, project_root: Path) -> bool:
    try:
        mp = resolve_module_ref(ref, project_root)
        return load_module(mp).name == target_name
    except Exception:
        return False


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--name", "-n", default=None, help="Module name (default: directory name)")
@click.option("--description", "-d", default=None, help="Module description (default: auto-detected from first H1)")
@click.option("--tags", "-t", default=None, help="Comma-separated tags (default: auto-detected)")
@click.option("--strategy", "-s", default=None,
              type=click.Choice(["heading", "fixed", "definition"]),
              help="Force a single chunking strategy for all files")
@click.option("--max-tokens", default=500, show_default=True, help="Max tokens per chunk")
@click.option("--overlap", default=50, show_default=True, help="Overlap tokens between chunks")
@click.option("--output", "-o", default=None, type=click.Path(), help="Write a module directory here")
@click.option("--install", is_flag=True, help="Install into .context/packed/ and register in config")
@click.option("--tool", "tools", multiple=True,
              type=click.Choice(["claude", "cursor", "copilot", "continue", "bob"]),
              help="Tool(s) to install for (with --install). Auto-detects if omitted.")
@click.option("--format", "-f", "fmt", default="jsonl",
              type=click.Choice(["jsonl", "text"]),
              help="Output format when writing to stdout")
@click.option("--project", "-p", default=".", type=click.Path(exists=True),
              help="Project root (for --install)")
def pack(directory, name, description, tags, strategy, max_tokens, overlap, output, install, tools, fmt, project):
    """Pack a directory of mixed files into a context module in one step.

    Scans DIRECTORY, extracts all supported file types to markdown, auto-selects
    chunking strategies, and outputs JSONL (default), a module directory (-o), or
    installs directly into the current project (--install).
    """
    from ctx.pack import pack as _pack
    from pathlib import Path

    input_dir = Path(directory).resolve()
    output_path = Path(output).resolve() if output else None
    project_root = Path(project).resolve()

    _pack(
        input_dir,
        name=name,
        description=description,
        tags=tags,
        strategy=strategy,
        max_tokens=max_tokens,
        overlap=overlap,
        output=output_path,
        install=install,
        tools=list(tools) if tools else None,
        fmt=fmt,
        project_root=project_root,
    )


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
