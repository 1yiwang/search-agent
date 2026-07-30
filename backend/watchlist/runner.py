"""Run a watchlist item through the research pipeline."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from agent import run_research
from config import config
from models import ResearchRequest
from report_store import load_report
from watchlist.delta import compare_reports
from watchlist.models import WatchDelta, WatchItem
from watchlist.store import get_watch, record_run_result


@contextmanager
def _recency_override(days: int):
    original = config.research_recency_days
    config.research_recency_days = days
    try:
        yield
    finally:
        config.research_recency_days = original


async def run_watch_item(
    watch_id: str,
    event_callback=None,
) -> tuple[WatchItem, WatchDelta | None]:
    """Execute research for a watch item, persist run + delta, return updated watch."""
    item = get_watch(watch_id)
    if item is None:
        raise ValueError(f"Watch not found: {watch_id}")
    if not item.enabled:
        raise ValueError(f"Watch disabled: {watch_id}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    started_at = datetime.now(timezone.utc).isoformat()
    prev_slug = item.latest_slug or item.baseline_slug
    prev_report = load_report(prev_slug) if prev_slug else None

    async def emit(event_type: str, data: dict):
        if event_callback:
            await event_callback(event_type, data)

    await emit("watch_run_start", {
        "watch_id": watch_id,
        "run_id": run_id,
        "topic": item.topic,
        "prev_slug": prev_slug,
        "recency_days": item.recency_days,
    })

    request = ResearchRequest(topic=item.topic, max_sources=item.max_sources)
    with _recency_override(item.recency_days):
        report = await run_research(request, event_callback=event_callback)

    delta = compare_reports(
        prev_report,
        report,
        watch_id=watch_id,
        run_id=run_id,
    )
    await emit("delta_ready", {
        "watch_id": watch_id,
        "run_id": run_id,
        "prev_slug": delta.prev_slug,
        "curr_slug": delta.curr_slug,
        "added": len(delta.added),
        "removed": len(delta.removed),
        "changed": len(delta.changed),
        "unchanged_count": delta.unchanged_count,
    })

    updated = record_run_result(
        watch_id,
        slug=report.slug,
        run_id=run_id,
        delta=delta,
        started_at=started_at,
    )
    if updated is None:
        raise ValueError(f"Failed to record run for watch: {watch_id}")

    await emit("watch_run_complete", {
        "watch_id": watch_id,
        "run_id": run_id,
        "slug": report.slug,
        "delta_id": delta.run_id,
        "baseline_slug": updated.baseline_slug,
        "latest_slug": updated.latest_slug,
    })
    return updated, delta
