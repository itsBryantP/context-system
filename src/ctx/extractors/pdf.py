"""PDF extractor — pdftotext (poppler) primary, PyMuPDF fallback."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ctx.extractors.base import Extractor
from ctx.schema import Source, SourceType


class PDFExtractor(Extractor):
    def can_handle(self, source: Source) -> bool:
        return source.type == SourceType.PDF

    def extract(self, source: Source, output_dir: Path) -> list[Path]:
        if not source.path:
            raise ValueError("PDF source requires a 'path'")

        pdf_path = Path(source.path).expanduser().resolve()
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / (pdf_path.stem + ".md")

        md = _extract_pdftotext(pdf_path) or _extract_pymupdf(pdf_path)
        if md is None:
            raise RuntimeError(
                f"Could not extract text from {pdf_path}. "
                "Install poppler-utils (pdftotext) or pymupdf."
            )

        out_path.write_text(md)
        return [out_path]


# ── pdftotext (poppler) ───────────────────────────────────────────────────────

def _extract_pdftotext(pdf_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _plain_text_to_markdown(result.stdout, pdf_path.stem)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _plain_text_to_markdown(text: str, title: str) -> str:
    """Wrap plain text output from pdftotext in a minimal markdown document."""
    lines = []
    prev_blank = True
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if not prev_blank:
                lines.append("")
            prev_blank = True
        else:
            lines.append(stripped)
            prev_blank = False
    body = "\n".join(lines).strip()
    return f"# {title}\n\n{body}\n"


# ── PyMuPDF ───────────────────────────────────────────────────────────────────

def _extract_pymupdf(pdf_path: Path) -> str | None:
    try:
        import fitz  # noqa: PLC0415
    except ImportError:
        return None

    try:
        doc = fitz.open(str(pdf_path))
        return _pymupdf_to_markdown(doc, pdf_path.stem)
    except Exception:
        return None


def _pymupdf_to_markdown(doc, title: str) -> str:
    """Convert a PyMuPDF document to markdown with font-size heading detection."""
    # First pass: collect all (size, text) spans to find body font size
    all_sizes: list[float] = []
    pages_spans: list[list[tuple[float, str]]] = []

    for page in doc:
        spans: list[tuple[float, str]] = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:  # skip image blocks
                continue
            for line in block.get("lines", []):
                line_texts: list[str] = []
                line_size: float = 0.0
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if t:
                        line_texts.append(t)
                        line_size = max(line_size, span["size"])
                if line_texts:
                    text = " ".join(line_texts)
                    all_sizes.append(line_size)
                    spans.append((line_size, text))
        pages_spans.append(spans)

    if not all_sizes:
        return f"# {title}\n"

    body_size = max(set(all_sizes), key=all_sizes.count)
    h1_min = body_size * 1.4
    h2_min = body_size * 1.15

    md_lines = [f"# {title}\n"]
    prev_text: str | None = None

    for spans in pages_spans:
        for size, text in spans:
            if text == prev_text:
                continue  # deduplicate repeated headers/footers
            prev_text = text

            if size >= h1_min:
                md_lines.append(f"\n## {text}")
            elif size >= h2_min:
                md_lines.append(f"\n### {text}")
            else:
                # Merge consecutive body lines into a paragraph
                if md_lines and md_lines[-1] and not md_lines[-1].startswith("#"):
                    md_lines[-1] += " " + text
                else:
                    md_lines.append(text)

    return "\n".join(md_lines) + "\n"
