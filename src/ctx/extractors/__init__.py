"""Extractor plugins for converting source formats to markdown."""

from ctx.extractors.base import Extractor
from ctx.extractors.markdown import MarkdownExtractor
from ctx.extractors.pdf import PDFExtractor
from ctx.extractors.pptx import PPTXExtractor
from ctx.extractors.url import URLExtractor
from ctx.schema import Source

_REGISTRY: list[Extractor] = [
    MarkdownExtractor(),
    PDFExtractor(),
    PPTXExtractor(),
    URLExtractor(),
]


def get_extractor(source: Source) -> Extractor:
    """Return the first extractor that can handle the given source."""
    for extractor in _REGISTRY:
        if extractor.can_handle(source):
            return extractor
    raise ValueError(f"No extractor registered for source type: {source.type!r}")
