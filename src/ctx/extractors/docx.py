from __future__ import annotations

import contextlib
import hashlib
import io
import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path

import yaml

from ctx.extractors.base import Extractor
from ctx.schema import Source, SourceType

_IMPORT_MSG = (
    "docling is required for DOCX extraction. "
    "Install with: uv pip install 'ctx-modules[extractors]'"
)


class ExtractionError(Exception):
    """Raised when extraction fails in a recoverable way (skip file and continue)."""
    pass


def _configure_docling_logging():
    """Suppress verbose Docling warnings (DrawingML, image loading, etc)."""
    docling_logger = logging.getLogger('docling')
    docling_logger.setLevel(logging.ERROR)


class DocxExtractor(Extractor):
    def __init__(self, remove_images: bool = True, filter_profile_icons: bool = True):
        self.remove_images = remove_images
        self.filter_profile_icons = filter_profile_icons
        self._converter = None
        _configure_docling_logging()

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
        
        try:
            content = _extract_docx(docx_path, self.converter, self.remove_images, self.filter_profile_icons)
            out_path.write_text(content)
        except ExtractionError:
            # Re-raise extraction errors as-is (user-friendly messages)
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ExtractionError(f"Unexpected error extracting {docx_path.name}: {type(e).__name__}: {e}")
        
        return [out_path]


def _extract_docx(docx_path: Path, converter, remove_images: bool, filter_profile_icons: bool) -> str:
    try:
        # Capture stderr to suppress Docling warnings (DrawingML, WMF, etc)
        stderr_capture = io.StringIO()
        with contextlib.redirect_stderr(stderr_capture):
            result = converter.convert(str(docx_path))
        
        # Log captured warnings at debug level
        warnings = stderr_capture.getvalue()
        if warnings:
            logger = logging.getLogger(__name__)
            logger.debug(f"Docling warnings for {docx_path.name}:\n{warnings}")
        
        markdown = result.document.export_to_markdown()

        if filter_profile_icons:
            markdown = _remove_profile_icons(markdown)
        elif remove_images:
            markdown = _remove_all_images(markdown)

        markdown = _normalize_whitespace(markdown)
        
        # Check for empty documents
        if len(markdown.strip()) < 10:
            raise ExtractionError(
                f"{docx_path.name} contains no extractable text content"
            )
        
        frontmatter = _build_frontmatter(result, docx_path)
        return f"{frontmatter}\n\n{markdown}"

    except zipfile.BadZipFile:
        raise ExtractionError(
            f"Invalid or corrupt DOCX file: {docx_path.name}. "
            f"The file may be damaged or in an unsupported format. "
            f"Try opening and re-saving in Microsoft Word."
        )
    
    except RuntimeError as e:
        error_msg = str(e).lower()
        if "could not load document" in error_msg or "not valid" in error_msg:
            raise ExtractionError(
                f"Docling could not load {docx_path.name}: {e}"
            )
        # Re-raise unknown RuntimeErrors
        raise

    except ExtractionError:
        # Re-raise our own errors as-is
        raise
    
    except Exception as e:
        raise ExtractionError(f"Failed to extract {docx_path.name}: {type(e).__name__}: {e}")


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
