"""URL extractor — fetches HTML and converts to markdown via markdownify."""

from __future__ import annotations

import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from ctx.extractors.base import Extractor
from ctx.schema import Source, SourceType

_IMPORT_MSG = (
    "markdownify is required for URL extraction. "
    "Install with: uv pip install 'ctx-modules[extractors]'"
)


class URLExtractor(Extractor):
    def can_handle(self, source: Source) -> bool:
        return source.type == SourceType.URL

    def extract(self, source: Source, output_dir: Path) -> list[Path]:
        if not source.url:
            raise ValueError("URL source requires a 'url'")

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / (_url_to_stem(source.url) + ".md")

        html = _fetch(source.url)
        md = _to_markdown(html)

        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        header = f"---\nsource_url: {source.url}\nfetched_at: {fetched_at}\n"
        if source.refresh:
            header += f"refresh: {source.refresh.value}\n"
        header += "---\n\n"

        out_path.write_text(header + md)
        return [out_path]


def _url_to_stem(url: str) -> str:
    """Derive a filesystem-safe stem from a URL."""
    parsed = urlparse(url)
    path_part = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
    stem = re.sub(r"[^\w.\-]", "-", path_part).strip("-") or "page"
    return stem[:80]  # guard against very long slugs


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ctx-extractor/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _to_markdown(html: str) -> str:
    try:
        import markdownify  # noqa: PLC0415
    except ImportError:
        raise ImportError(_IMPORT_MSG)

    return markdownify.markdownify(
        html,
        heading_style="ATX",
        strip=["script", "style", "nav", "footer", "header"],
    )
