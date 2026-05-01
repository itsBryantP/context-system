from __future__ import annotations

from pathlib import Path

from ctx.extractors.base import Extractor
from ctx.schema import Source, SourceType


class DocxExtractor(Extractor):
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
        
        out_path.write_text(f"# {docx_path.stem}\n\nDOCX extraction placeholder\n")
        return [out_path]
