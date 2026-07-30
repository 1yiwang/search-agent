"""File-based watchlist persistence under data/watchlists/."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import config
from watchlist.models import WatchCreate, WatchDelta, WatchItem, WatchUpdate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def watchlist_root() -> Path:
    return Path(config.watchlist_dir)


def _index_path() -> Path:
    return watchlist_root() / "index.json"


def _watch_dir(watch_id: str) -> Path:
    return watchlist_root() / watch_id


def _watch_path(watch_id: str) -> Path:
    return _watch_dir(watch_id) / "watch.json"


def _runs_path(watch_id: str) -> Path:
    return _watch_dir(watch_id) / "runs.jsonl"


def _deltas_dir(watch_id: str) -> Path:
    return _watch_dir(watch_id) / "deltas"


def _slugify_topic(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return (slug[:40] or "watch")


def _read_index() -> list[str]:
    path = _index_path()
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return list(raw.get("ids") or [])


def _write_index(ids: list[str]) -> None:
    root = watchlist_root()
    root.mkdir(parents=True, exist_ok=True)
    _index_path().write_text(
        json.dumps({"ids": ids}, indent=2),
        encoding="utf-8",
    )


def _save_watch(item: WatchItem) -> None:
    d = _watch_dir(item.id)
    d.mkdir(parents=True, exist_ok=True)
    _deltas_dir(item.id).mkdir(parents=True, exist_ok=True)
    _watch_path(item.id).write_text(
        item.model_dump_json(indent=2),
        encoding="utf-8",
    )


def create_watch(payload: WatchCreate) -> WatchItem:
    watch_id = f"{_slugify_topic(payload.topic)}-{uuid.uuid4().hex[:8]}"
    item = WatchItem(
        id=watch_id,
        topic=payload.topic.strip(),
        max_sources=payload.max_sources,
        cadence=payload.cadence,
        recency_days=payload.recency_days,
        baseline_slug=payload.baseline_slug or "",
        latest_slug=payload.baseline_slug or "",
        created_at=_now_iso(),
        enabled=True,
    )
    _save_watch(item)
    ids = _read_index()
    if watch_id not in ids:
        ids.insert(0, watch_id)
        _write_index(ids)
    return item


def get_watch(watch_id: str) -> WatchItem | None:
    path = _watch_path(watch_id)
    if not path.is_file():
        return None
    return WatchItem.model_validate_json(path.read_text(encoding="utf-8"))


def list_watches() -> list[WatchItem]:
    items: list[WatchItem] = []
    for watch_id in _read_index():
        item = get_watch(watch_id)
        if item is not None:
            items.append(item)
    return items


def update_watch(watch_id: str, payload: WatchUpdate) -> WatchItem | None:
    item = get_watch(watch_id)
    if item is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    updated = item.model_copy(update=data)
    _save_watch(updated)
    return updated


def delete_watch(watch_id: str) -> bool:
    path = _watch_path(watch_id)
    if not path.is_file():
        return False
    # Remove watch.json; leave runs/deltas for audit (or wipe dir).
    import shutil

    shutil.rmtree(_watch_dir(watch_id), ignore_errors=True)
    ids = [i for i in _read_index() if i != watch_id]
    _write_index(ids)
    return True


def append_run(
    watch_id: str,
    *,
    run_id: str,
    slug: str,
    delta_id: str = "",
    started_at: str = "",
    completed_at: str = "",
) -> None:
    line = {
        "run_id": run_id,
        "slug": slug,
        "delta_id": delta_id,
        "started_at": started_at or _now_iso(),
        "completed_at": completed_at or _now_iso(),
    }
    path = _runs_path(watch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def save_delta(delta: WatchDelta) -> Path:
    d = _deltas_dir(delta.watch_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{delta.run_id}.json"
    path.write_text(delta.model_dump_json(indent=2), encoding="utf-8")
    md_path = d / f"{delta.run_id}.md"
    if delta.summary_markdown:
        md_path.write_text(delta.summary_markdown, encoding="utf-8")
    return path


def load_latest_delta(watch_id: str) -> WatchDelta | None:
    item = get_watch(watch_id)
    if item is None:
        return None
    if item.latest_delta_id:
        path = _deltas_dir(watch_id) / f"{item.latest_delta_id}.json"
        if path.is_file():
            return WatchDelta.model_validate_json(path.read_text(encoding="utf-8"))
    d = _deltas_dir(watch_id)
    if not d.is_dir():
        return None
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return WatchDelta.model_validate_json(files[0].read_text(encoding="utf-8"))


def record_run_result(
    watch_id: str,
    *,
    slug: str,
    run_id: str,
    delta: WatchDelta | None,
    started_at: str,
) -> WatchItem | None:
    item = get_watch(watch_id)
    if item is None:
        return None
    updates: dict = {
        "latest_slug": slug,
        "last_run_at": _now_iso(),
    }
    if not item.baseline_slug:
        updates["baseline_slug"] = slug
    delta_id = ""
    if delta is not None:
        save_delta(delta)
        delta_id = delta.run_id
        updates["latest_delta_id"] = delta_id
    updated = item.model_copy(update=updates)
    _save_watch(updated)
    append_run(
        watch_id,
        run_id=run_id,
        slug=slug,
        delta_id=delta_id,
        started_at=started_at,
        completed_at=updates["last_run_at"],
    )
    return updated
