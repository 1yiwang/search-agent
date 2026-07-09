"""Build per-URL text snapshots for in-app citation preview."""
import re
from urllib.parse import urlparse

from dedup import normalize_url
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


def _clean_snapshot_text(text: str) -> str:
    """Normalize whitespace and trim likely navigation noise at the top."""
    if not text:
        return ""

    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned: list[str] = []
    for ln in lines:
        if not ln.strip():
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(ln)

    while cleaned and cleaned[0] == "":
        cleaned.pop(0)

    joined = "\n".join(cleaned).strip()
    head = joined[:500]
    if head and len(re.findall(r"[A-Za-z\u00c0-\u024f\u4e00-\u9fff]", head)) < 40:
        cut = joined.find("\n\n", 200)
        if cut > 0:
            joined = joined[cut:].lstrip()

    return joined


def build_source_snapshots(results: list[SearchResult]) -> list[SourceSnapshot]:
    """One snapshot per unique URL from fetched search results."""
    by_norm: dict[str, SourceSnapshot] = {}
    for result in results:
        url = result.url.strip()
        if not url:
            continue
        norm = normalize_url(url)
        if norm in by_norm:
            continue
        text = (result.full_text or result.snippet or "").strip()
        if text.startswith("[Failed"):
            text = ""
        text = _clean_snapshot_text(text)
        if len(text) > MAX_SNAPSHOT_CHARS:
            text = text[:MAX_SNAPSHOT_CHARS] + "\n\n[… truncated …]"
        by_norm[norm] = SourceSnapshot(
            url=url,
            title=(result.title or url).strip(),
            content_kind=_content_kind(url, text),
            text=text,
            normalized_url=norm,
        )
    return list(by_norm.values())
