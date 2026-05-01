from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

import yaml

from ctx.extractors.base import Extractor
from ctx.schema import Source, SourceType

_IMPORT_MSG = (
    "docling is required for DOCX extraction. "
    "Install with: uv pip install 'ctx-modules[extractors]'"
)


class DocxExtractor(Extractor):
    def __init__(self, remove_images: bool = True, filter_profile_icons: bool = True):
        self.remove_images = remove_images
        self.filter_profile_icons = filter_profile_icons
        self._converter = None

    @property
    def converter(self):
        if self._converter is None:
            try:
                from docling.document_converter import DocumentConverter  # noqa: PLC0415
            except ImportError:
                raise ImportError(_IMPORT_MSG)
            self._converter = DocumentConverter()
        return self._converter

    def can_handle(self, source: Source) -> bool:
        return source.type == SourceType.DOCX

    def extract(self, source: Source, output_dir: Path) -> list[Path]:
        if not source.path:
            raise ValueError("DOCX source requires a 'path'")

        docx_path = Path(source.path).expanduser().resolve()
        if not docx_path.exists():
            raise FileNotFoundError(f"DOCX not found: {docx_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / (docx_path.stem + ".md")
        out_path.write_text(_extract_docx(docx_path, self.converter, self.remove_images, self.filter_profile_icons))
        return [out_path]


def _extract_docx(docx_path: Path, converter, remove_images: bool, filter_profile_icons: bool) -> str:
    try:
        result = converter.convert(str(docx_path))
        markdown = result.document.export_to_markdown()

        if filter_profile_icons:
            markdown = _remove_profile_icons(markdown)
        elif remove_images:
            markdown = _remove_all_images(markdown)

        markdown = _normalize_whitespace(markdown)
        
        frontmatter = _build_frontmatter(result, docx_path)
        return f"{frontmatter}\n\n{markdown}"

    except Exception as e:
        raise RuntimeError(f"Failed to extract {docx_path}: {e}")


def _remove_profile_icons(markdown: str) -> str:
    return re.sub(r"<!--\s*image\s*-->", "", markdown, flags=re.IGNORECASE)


def _remove_all_images(markdown: str) -> str:
    markdown = re.sub(r"!\[.*?\]\(.*?\)", "", markdown)
    markdown = re.sub(r"<!--\s*image\s*-->", "", markdown, flags=re.IGNORECASE)
    return markdown


def _normalize_whitespace(markdown: str) -> str:
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _build_frontmatter(result, source: Path) -> str:
    metadata = {}
    
    if hasattr(result.document, 'title') and result.document.title:
        metadata['doc_title'] = result.document.title
    if hasattr(result.document, 'author') and result.document.author:
        metadata['doc_author'] = result.document.author
    
    metadata['file_hash'] = _compute_hash(source)
    metadata['file_size'] = source.stat().st_size
    metadata['modified_at'] = datetime.fromtimestamp(source.stat().st_mtime).isoformat()
    metadata['converted_at'] = datetime.utcnow().isoformat()
    metadata['converter'] = 'docling'
    metadata['source_type'] = 'docx'
    
    yaml_str = yaml.dump(metadata, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---"


def _compute_hash(source: Path) -> str:
    return hashlib.sha256(source.read_bytes()).hexdigest()
