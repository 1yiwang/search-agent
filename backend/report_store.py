"""Persist and load research reports from disk + memory cache."""
import json
from pathlib import Path

from config import config
from models import ResearchReport

_cache: dict[str, ResearchReport] = {}


def report_json_path(slug: str) -> Path:
    return Path(config.report_output_dir) / slug / "data.json"


def persist_report(report: ResearchReport) -> Path:
    """Write report JSON to reports/<slug>/data.json."""
    path = report_json_path(report.slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    _cache[report.slug] = report
    return path


def cache_report(report: ResearchReport) -> None:
    """Update in-memory cache (disk write happens via deploy/persist)."""
    _cache[report.slug] = report


def load_report(slug: str) -> ResearchReport | None:
    """Load report from memory cache, then reports/<slug>/data.json."""
    if slug in _cache:
        return _cache[slug]

    path = report_json_path(slug)
    if not path.is_file():
        return None

    report = ResearchReport.model_validate_json(path.read_text(encoding="utf-8"))
    _cache[slug] = report
    return report


def clear_cache() -> None:
    """Clear memory cache (for tests)."""
    _cache.clear()


def list_reports(limit: int = 30) -> list[dict]:
    """List saved reports newest first (from reports/*/data.json)."""
    base = Path(config.report_output_dir)
    if not base.is_dir():
        return []

    candidates = [
        d for d in base.iterdir()
        if d.is_dir() and (d / "data.json").is_file()
    ]
    candidates.sort(
        key=lambda p: (p / "data.json").stat().st_mtime,
        reverse=True,
    )

    summaries: list[dict] = []
    for report_dir in candidates[:limit]:
        try:
            raw = json.loads((report_dir / "data.json").read_text(encoding="utf-8"))
            meta = raw.get("metadata") or {}
            summaries.append({
                "slug": raw.get("slug") or report_dir.name,
                "topic": raw.get("topic") or report_dir.name,
                "fact_count": len(raw.get("facts") or []),
                "completed_at": meta.get("completed_at") or "",
                "html_url": raw.get("html_url") or f"/research/{report_dir.name}/",
            })
        except (json.JSONDecodeError, OSError):
            continue
    return summaries
