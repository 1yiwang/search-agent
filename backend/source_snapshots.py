"""Build per-URL text snapshots for in-app citation preview."""
from urllib.parse import urlparse

from models import SearchResult, SourceSnapshot

DOCUMENT_EXTENSIONS = (".docx", ".doc", ".pdf", ".xlsx", ".xls", ".pptx", ".ppt")
MAX_SNAPSHOT_CHARS = 12_000


def _content_kind(url: str, text: str) -> str:
    path = urlparse(url).path.lower()
    if any(path.endswith(ext) for ext in DOCUMENT_EXTENSIONS):
        return "document"
    if not text:
        return "empty"
    return "html"


def build_source_snapshots(results: list[SearchResult]) -> list[SourceSnapshot]:
    """One snapshot per unique URL from fetched search results."""
    by_url: dict[str, SourceSnapshot] = {}
    for result in results:
        url = result.url.strip()
        if not url or url in by_url:
            continue
        text = (result.full_text or result.snippet or "").strip()
        if text.startswith("[Failed"):
            text = ""
        if len(text) > MAX_SNAPSHOT_CHARS:
            text = text[:MAX_SNAPSHOT_CHARS] + "\n\n[… truncated …]"
        by_url[url] = SourceSnapshot(
            url=url,
            title=(result.title or url).strip(),
            content_kind=_content_kind(url, text),
            text=text,
        )
    return list(by_url.values())
