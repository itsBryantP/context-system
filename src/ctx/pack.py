"""ctx pack — zero-config module packaging from any directory."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ── File classification ───────────────────────────────────────────────────────

_EXT_MAP: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "plaintext",
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".ppt": "unsupported",  # legacy binary format; python-pptx requires .pptx
    ".boxnote": "boxnote",
    ".html": "html",
    ".htm": "html",
    ".yaml": "structured",
    ".yml": "structured",
    ".json": "structured",
}


@dataclass
class ScanResult:
    """A single file discovered during directory scanning."""
    source_path: Path
    classification: str  # markdown | plaintext | pdf | pptx | html | structured | unsupported


def scan_directory(input_dir: Path) -> list[ScanResult]:
    """Recursively scan input_dir and classify every file by extension.

    Rules:
    - Hidden files and directories (name starts with '.' or '_') are skipped.
    - Files are sorted by path for deterministic output.
    - Returns all files, including unsupported ones (callers decide what to skip).
    """
    input_dir = input_dir.resolve()
    results: list[ScanResult] = []

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        # Skip anything inside a hidden or underscore-prefixed directory
        if any(part.startswith((".", "_")) for part in path.relative_to(input_dir).parts):
            continue
        classification = _EXT_MAP.get(path.suffix.lower(), "unsupported")
        results.append(ScanResult(source_path=path, classification=classification))

    return results


# ── Strategy auto-selection ───────────────────────────────────────────────────


def select_strategy(content: str, max_tokens: int = 500) -> "ChunkingStrategy":
    """Analyze markdown content and return the most appropriate chunking strategy.

    Heuristic (from PACK_SPEC.md):
    - Entire file fits in one chunk → FIXED (strategy doesn't matter)
    - Many bold-definition patterns, more than H2 headings → DEFINITION
    - Many H3/H4 headings, more than 2× the H2 count → DEFINITION
    - Two or more H2 headings → HEADING
    - Otherwise → FIXED
    """
    from ctx.chunker.base import count_tokens  # noqa: PLC0415
    from ctx.schema import ChunkingStrategy  # noqa: PLC0415

    if count_tokens(content) <= max_tokens:
        return ChunkingStrategy.FIXED

    headings_h2 = len(re.findall(r"^## .+", content, re.MULTILINE))
    headings_h3h4 = len(re.findall(r"^#{3,4} .+", content, re.MULTILINE))
    bold_defs = len(re.findall(r"\*\*[^*]+\*\*\s*[:\u2014–-]", content))

    if bold_defs >= 3 and bold_defs > headings_h2:
        return ChunkingStrategy.DEFINITION

    if headings_h3h4 >= 3 and headings_h3h4 > headings_h2 * 2:
        return ChunkingStrategy.DEFINITION

    if headings_h2 >= 2:
        return ChunkingStrategy.HEADING

    return ChunkingStrategy.FIXED


def build_strategy_map(
    extracted_files: "list[ExtractedFile]",
    max_tokens: int = 500,
    override: "ChunkingStrategy | None" = None,
) -> "dict[Path, ChunkingStrategy]":
    """Return a mapping from each extracted file's md_path to its chunking strategy.

    If override is set, every file gets that strategy regardless of content.
    """
    from ctx.schema import ChunkingStrategy  # noqa: PLC0415

    result: dict[Path, ChunkingStrategy] = {}
    for ef in extracted_files:
        if override is not None:
            result[ef.md_path] = override
        else:
            content = ef.md_path.read_text(encoding="utf-8", errors="replace")
            result[ef.md_path] = select_strategy(content, max_tokens)
    return result


# ── Extraction ────────────────────────────────────────────────────────────────


@dataclass
class ExtractedFile:
    """A single file successfully extracted to markdown in temp space."""
    original_path: Path
    md_path: Path
    classification: str


def extract_files(
    scan_results: list[ScanResult],
    input_dir: Path,
    tmp_dir: Path,
) -> tuple[list[ExtractedFile], list[tuple[Path, str]]]:
    """Extract every scanned file to markdown in tmp_dir.

    Returns (extracted, failures) where failures is a list of (path, reason).
    The input directory is never modified.
    """
    extracted: list[ExtractedFile] = []
    failures: list[tuple[Path, str]] = []

    for result in scan_results:
        if result.classification == "unsupported":
            continue
        try:
            md_path = _extract_one(result, input_dir, tmp_dir)
            extracted.append(ExtractedFile(
                original_path=result.source_path,
                md_path=md_path,
                classification=result.classification,
            ))
        except Exception as exc:
            failures.append((result.source_path, str(exc)))

    return extracted, failures


def _unique_md_path(source_path: Path, input_dir: Path, tmp_dir: Path) -> Path:
    """Derive a unique output .md path in tmp_dir that avoids collisions."""
    rel = source_path.relative_to(input_dir)
    # flatten: subdir/file.pdf → subdir__file.md
    flat = "__".join(rel.with_suffix(".md").parts)
    return tmp_dir / flat


def _extract_one(result: ScanResult, input_dir: Path, tmp_dir: Path) -> Path:
    """Dispatch to the right handler and return the path of the written .md file."""
    cls = result.classification
    src = result.source_path
    out = _unique_md_path(src, input_dir, tmp_dir)

    if cls == "markdown":
        return _extract_markdown(src, out)
    if cls == "plaintext":
        return _extract_plaintext(src, out)
    if cls == "pdf":
        return _extract_pdf(src, out)
    if cls == "pptx":
        return _extract_pptx_file(src, out)
    if cls == "boxnote":
        return _extract_boxnote(src, out)
    if cls == "html":
        return _extract_html(src, out)
    if cls == "structured":
        return _extract_structured(src, out)
    raise ValueError(f"Unknown classification: {cls}")


def _extract_markdown(src: Path, out: Path) -> Path:
    from ctx.extractors.markdown import _strip_frontmatter  # noqa: PLC0415
    body, _ = _strip_frontmatter(src.read_text(encoding="utf-8", errors="replace"))
    out.write_text(body, encoding="utf-8")
    return out


def _extract_plaintext(src: Path, out: Path) -> Path:
    content = src.read_text(encoding="utf-8", errors="replace")
    out.write_text(f"# {src.stem}\n\n{content}", encoding="utf-8")
    return out


def _extract_pdf(src: Path, out: Path) -> Path:
    from ctx.extractors.pdf import _extract_pdftotext, _extract_pymupdf  # noqa: PLC0415
    md = _extract_pdftotext(src) or _extract_pymupdf(src)
    if md is None:
        raise RuntimeError(
            f"Could not extract text from {src.name}. "
            "Install poppler-utils (pdftotext) or pymupdf."
        )
    out.write_text(md, encoding="utf-8")
    return out


def _extract_pptx_file(src: Path, out: Path) -> Path:
    from ctx.extractors.pptx import _extract_pptx  # noqa: PLC0415
    out.write_text(_extract_pptx(src), encoding="utf-8")
    return out


def _extract_boxnote(src: Path, out: Path) -> Path:
    import json  # noqa: PLC0415

    try:
        data = json.loads(src.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse Box Note JSON: {exc}") from exc

    doc = data.get("doc", {})
    lines: list[str] = [f"# {src.stem}", ""]

    def render(node: object, list_depth: int = 0, ordered: bool = False, index: int = 1) -> None:
        if not isinstance(node, dict):
            return
        ntype = node.get("type", "")
        children = node.get("content") or []

        if ntype == "heading":
            level = node.get("attrs", {}).get("level", 2)
            prefix = "#" * (level + 1)  # shift down one so doc title stays H1
            text = _boxnote_inline_text(children)
            if text:
                lines.append(f"\n{prefix} {text}")
        elif ntype == "paragraph":
            text = _boxnote_inline_text(children)
            if text:
                lines.append(text)
            else:
                lines.append("")
        elif ntype in ("bullet_list", "check_list"):
            for child in children:
                render(child, list_depth=list_depth, ordered=False)
        elif ntype == "ordered_list":
            for i, child in enumerate(children, 1):
                render(child, list_depth=list_depth, ordered=True, index=i)
        elif ntype in ("list_item", "check_list_item"):
            indent = "  " * list_depth
            marker = f"{index}." if ordered else "-"
            # first paragraph becomes the list item text; nested lists recurse
            first = True
            for child in children:
                if child.get("type") == "paragraph":
                    text = _boxnote_inline_text(child.get("content") or [])
                    if first and text:
                        lines.append(f"{indent}{marker} {text}")
                        first = False
                    elif text:
                        lines.append(f"{indent}  {text}")
                else:
                    render(child, list_depth=list_depth + 1)
        elif ntype == "horizontal_rule":
            lines.append("\n---")
        else:
            # doc, unknown block types — just recurse into children
            for child in children:
                render(child, list_depth=list_depth)

    for node in doc.get("content") or []:
        render(node)

    # Collapse runs of more than one blank line
    collapsed: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        collapsed.append(line)
        prev_blank = is_blank

    out.write_text("\n".join(collapsed).strip() + "\n", encoding="utf-8")
    return out


def _boxnote_inline_text(nodes: list) -> str:
    """Concatenate text from inline content nodes, preserving bold marks."""
    parts: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "text":
            text = node.get("text", "")
            marks = {m["type"] for m in node.get("marks", []) if isinstance(m, dict)}
            if "bold" in marks:
                text = f"**{text}**"
            if "italic" in marks:
                text = f"*{text}*"
            if "code" in marks:
                text = f"`{text}`"
            parts.append(text)
        elif node.get("type") == "hard_break":
            parts.append("\n")
    return "".join(parts)


def _extract_html(src: Path, out: Path) -> Path:
    try:
        import markdownify  # noqa: PLC0415
    except ImportError:
        raise RuntimeError(
            f"markdownify is required for HTML extraction. "
            "Install with: uv pip install 'ctx-modules[extractors]'"
        )
    html = src.read_text(encoding="utf-8", errors="replace")
    md = markdownify.markdownify(html, heading_style="ATX")
    out.write_text(md, encoding="utf-8")
    return out


def _extract_structured(src: Path, out: Path) -> Path:
    content = src.read_text(encoding="utf-8", errors="replace")
    lang = "yaml" if src.suffix.lower() in {".yaml", ".yml"} else "json"
    md = f"# {src.name}\n\n```{lang}\n{content}\n```\n"
    out.write_text(md, encoding="utf-8")
    return out


# ── Name normalization ────────────────────────────────────────────────────────

def kebab_case(name: str) -> str:
    """Normalize a directory name to a valid kebab-case module name.

    Examples:
        "API Knowledge Base"  →  "api-knowledge-base"
        "My_Docs"             →  "my-docs"
        "v2_api_specs"        →  "v2-api-specs"
        "  hello--world  "    →  "hello-world"
    """
    name = name.strip()
    # Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)
    # Strip characters that aren't alphanumeric or hyphens
    name = re.sub(r"[^\w-]", "", name)
    # Collapse multiple hyphens
    name = re.sub(r"-{2,}", "-", name)
    # Lowercase and strip leading/trailing hyphens
    return name.lower().strip("-")


# ── Auto-detection (name, description, tags) ─────────────────────────────────

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "as", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "not", "no", "nor", "so", "yet", "both", "either", "this", "that",
    "these", "those", "it", "its", "their", "our", "your", "my", "his",
    "her", "we", "you", "they", "he", "she", "all", "any", "each",
    "more", "also", "into", "then", "than", "about", "over", "after",
})


def infer_name(input_dir: Path, override: str | None = None) -> str:
    """Return the module name: override if given, otherwise kebab-case of the dir name."""
    if override:
        return kebab_case(override)
    return kebab_case(input_dir.name)


def infer_description(md_contents: list[str], dir_name: str) -> str:
    """Return a one-line description.

    Uses the text of the first H1 heading found across all documents.
    Falls back to a generic string if no H1 is found.
    """
    for content in md_contents:
        m = re.search(r"^# (.+)", content, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return f"Context module packed from {dir_name}"


def infer_tags(md_contents: list[str], override: str | None = None) -> list[str]:
    """Return a list of 3–5 representative tags.

    If override is given (comma-separated string), split and return those.
    Otherwise, collect terms from H1–H3 headings and **bold** spans across all
    documents, count per-document frequency, and return the top terms that
    appear in at least 2 documents. Falls back to [] if fewer than 2 qualify.
    """
    if override:
        return [t.strip() for t in override.split(",") if t.strip()]

    # Collect candidate terms per document
    per_doc: list[set[str]] = []
    for content in md_contents:
        terms: set[str] = set()
        # H1–H3 heading texts
        for m in re.finditer(r"^#{1,3} (.+)", content, re.MULTILINE):
            terms.update(_tokenize(m.group(1)))
        # **bold** spans
        for m in re.finditer(r"\*\*([^*]+)\*\*", content):
            terms.update(_tokenize(m.group(1)))
        per_doc.append(terms)

    if not per_doc:
        return []

    # Count how many documents each term appears in
    doc_freq: dict[str, int] = {}
    for terms in per_doc:
        for t in terms:
            doc_freq[t] = doc_freq.get(t, 0) + 1

    # Keep terms in 2+ docs, sort by frequency descending then alphabetically
    candidates = [
        (freq, term)
        for term, freq in doc_freq.items()
        if freq >= 2 and len(term) >= 3 and term not in _STOP_WORDS
    ]
    candidates.sort(key=lambda x: (-x[0], x[1]))

    tags = [term for _, term in candidates[:5]]
    return tags if len(tags) >= 2 else []


def _tokenize(text: str) -> list[str]:
    """Split heading/bold text into lowercase words, dropping stop words and short words."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text.lower())
    return [w for w in words if len(w) >= 3 and w not in _STOP_WORDS]


# ── Chunking ──────────────────────────────────────────────────────────────────


def chunk_files(
    extracted_files: list[ExtractedFile],
    strategies: "dict[Path, ChunkingStrategy]",
    module_name: str,
    tags: list[str],
    max_tokens: int = 500,
    overlap: int = 50,
    input_dir: Path | None = None,
) -> "list[Chunk]":
    """Chunk all extracted files using their assigned strategies.

    source_file on each Chunk is the original input path relative to input_dir,
    not the temp-extracted .md path.
    """
    from ctx.chunker.definition import DefinitionChunker  # noqa: PLC0415
    from ctx.chunker.fixed import FixedChunker  # noqa: PLC0415
    from ctx.chunker.heading import HeadingChunker  # noqa: PLC0415
    from ctx.chunker.base import Chunk  # noqa: PLC0415
    from ctx.schema import ChunkingStrategy  # noqa: PLC0415

    _chunkers = {
        ChunkingStrategy.HEADING: HeadingChunker(),
        ChunkingStrategy.FIXED: FixedChunker(),
        ChunkingStrategy.DEFINITION: DefinitionChunker(),
    }

    all_chunks: list[Chunk] = []
    for ef in extracted_files:
        strategy = strategies.get(ef.md_path, ChunkingStrategy.FIXED)
        chunker = _chunkers[strategy]

        if input_dir is not None:
            try:
                source_file = str(ef.original_path.relative_to(input_dir))
            except ValueError:
                source_file = ef.original_path.name
        else:
            source_file = ef.original_path.name

        content = ef.md_path.read_text(encoding="utf-8", errors="replace")
        chunks = chunker.chunk(
            content,
            module_name=module_name,
            source_file=source_file,
            tags=tags,
            version="0.1.0",
            max_tokens=max_tokens,
            overlap_tokens=overlap,
        )
        all_chunks.extend(chunks)

    return all_chunks


def majority_strategy(strategies: "dict[Path, ChunkingStrategy]") -> "ChunkingStrategy":
    """Return the most frequently used strategy. Ties broken by enum declaration order."""
    from ctx.schema import ChunkingStrategy  # noqa: PLC0415

    if not strategies:
        return ChunkingStrategy.HEADING

    counts: dict[ChunkingStrategy, int] = {}
    for s in strategies.values():
        counts[s] = counts.get(s, 0) + 1

    return max(counts, key=lambda s: counts[s])


# ── Module output ─────────────────────────────────────────────────────────────

_CLS_TO_SOURCE_TYPE: dict[str, str] = {
    "markdown": "markdown",
    "plaintext": "markdown",
    "html": "markdown",
    "structured": "markdown",
    "pdf": "pdf",
    "pptx": "pptx",
}


def write_module(
    output_path: Path,
    name: str,
    description: str,
    tags: list[str],
    extracted_files: list[ExtractedFile],
    strategies: "dict[Path, ChunkingStrategy]",
    chunks: "list[Chunk]",
    max_tokens: int,
    overlap: int,
) -> None:
    """Write a complete module directory to output_path.

    Layout:
        output_path/
            module.yaml          — auto-detected config + sources + overrides
            content/             — extracted .md files
            chunks/<name>.jsonl  — pre-built JSONL
    """
    import yaml  # noqa: PLC0415
    from ctx.schema import (  # noqa: PLC0415
        ChunkingConfig,
        ChunkingOverride,
        ModuleConfig,
        Source,
        SourceType,
    )
    from ctx.integrations.jsonl import write_jsonl  # noqa: PLC0415

    if output_path.exists():
        raise FileExistsError(f"Output path already exists: {output_path}")

    dom = majority_strategy(strategies)

    overrides: list[ChunkingOverride] = []
    for ef in extracted_files:
        file_strategy = strategies.get(ef.md_path)
        if file_strategy is not None and file_strategy != dom:
            overrides.append(ChunkingOverride(
                pattern=f"content/{ef.md_path.name}",
                strategy=file_strategy,
            ))

    sources = [
        Source(
            type=SourceType(_CLS_TO_SOURCE_TYPE.get(ef.classification, "markdown")),
            path=str(ef.original_path),
        )
        for ef in extracted_files
    ]

    chunking = ChunkingConfig(
        strategy=dom,
        max_tokens=max_tokens,
        overlap_tokens=overlap,
        overrides=overrides,
    )
    mod = ModuleConfig(
        name=name,
        description=description,
        tags=tags,
        sources=sources,
        chunking=chunking,
    )

    output_path.mkdir(parents=True)
    content_dir = output_path / "content"
    content_dir.mkdir()

    for ef in extracted_files:
        dest = content_dir / ef.md_path.name
        dest.write_text(ef.md_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    yaml_data = mod.model_dump(mode="json", exclude_defaults=False)
    (output_path / "module.yaml").write_text(
        yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
    )

    write_jsonl(chunks, output_path / "chunks" / f"{name}.jsonl")


# ── Orchestrator ──────────────────────────────────────────────────────────────


def pack(
    input_dir: Path,
    *,
    name: str | None = None,
    description: str | None = None,
    tags: str | None = None,
    strategy: str | None = None,
    max_tokens: int = 500,
    overlap: int = 50,
    output: Path | None = None,
    install: bool = False,
    tools: list[str] | None = None,
    fmt: str = "jsonl",
    project_root: Path | None = None,
) -> "list[Chunk]":
    """Run the full pack pipeline on input_dir.

    Progress messages go to stderr. Chunk output (stdout/text mode) goes to stdout.
    Returns the list of Chunk objects produced.
    """
    import tempfile  # noqa: PLC0415

    import click  # noqa: PLC0415

    from ctx.chunker.base import Chunk  # noqa: PLC0415
    from ctx.integrations.jsonl import chunks_to_jsonl  # noqa: PLC0415
    from ctx.schema import ChunkingStrategy  # noqa: PLC0415

    # 1. Scan
    scan_results = scan_directory(input_dir)
    supported = [r for r in scan_results if r.classification != "unsupported"]
    skipped_count = len(scan_results) - len(supported)
    click.echo(
        f"Scanned {len(scan_results)} files: {len(supported)} supported, "
        f"{skipped_count} skipped",
        err=True,
    )

    with tempfile.TemporaryDirectory() as _tmp:
        tmp_dir = Path(_tmp)

        # 2. Extract
        extracted, failures = extract_files(scan_results, input_dir, tmp_dir)
        for path, reason in failures:
            click.echo(f"  Warning: skipped {path.name}: {reason}", err=True)
        click.echo(
            f"Extracted {len(extracted)} files"
            + (f" ({len(failures)} failed)" if failures else ""),
            err=True,
        )

        # 3. Infer metadata
        md_contents = [
            ef.md_path.read_text(encoding="utf-8", errors="replace")
            for ef in extracted
        ]
        mod_name = infer_name(input_dir, override=name)
        mod_description = description or infer_description(md_contents, input_dir.name)
        mod_tags = infer_tags(md_contents, override=tags)

        # 4. Strategy selection
        override_strategy = ChunkingStrategy(strategy) if strategy else None
        strategies = build_strategy_map(extracted, max_tokens=max_tokens, override=override_strategy)

        # 5. Chunk
        all_chunks: list[Chunk] = chunk_files(
            extracted, strategies, mod_name, mod_tags,
            max_tokens=max_tokens, overlap=overlap, input_dir=input_dir,
        )
        click.echo(
            f"Chunked into {len(all_chunks)} chunks from {len(extracted)} files",
            err=True,
        )

        # 6. Output
        if output is not None:
            write_module(
                output, mod_name, mod_description, mod_tags,
                extracted, strategies, all_chunks, max_tokens, overlap,
            )
            click.echo(f"Module written to {output}", err=True)

        elif install:
            import shutil  # noqa: PLC0415
            _project_root = project_root or Path.cwd()
            packed_dir = _project_root / ".context" / "packed" / mod_name
            if packed_dir.exists():
                shutil.rmtree(packed_dir)
            write_module(
                packed_dir, mod_name, mod_description, mod_tags,
                extracted, strategies, all_chunks, max_tokens, overlap,
            )
            from ctx.integrations.claude_code import install_module  # noqa: PLC0415
            from ctx.config import load_config, save_config  # noqa: PLC0415
            from ctx.schema import ModuleRef  # noqa: PLC0415

            install_module(packed_dir, _project_root, tools=tools)
            config = load_config(_project_root)
            ref_path = str(packed_dir)
            if not any(m.path == ref_path for m in config.modules):
                config.modules.append(ModuleRef(path=ref_path))
                save_config(_project_root, config)
            click.echo(f"Installed module '{mod_name}' at {packed_dir}", err=True)

        else:
            if fmt == "jsonl":
                click.echo(chunks_to_jsonl(all_chunks), nl=False)
            else:
                for chunk in all_chunks:
                    click.echo(
                        f"--- [{chunk.id}] "
                        f"({chunk.metadata.get('token_count', '?')} tokens) ---"
                    )
                    click.echo(chunk.content)
                    click.echo()

        return all_chunks
