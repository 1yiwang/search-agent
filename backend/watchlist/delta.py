"""Deterministic report delta for watchlist runs (Step 41c)."""

from __future__ import annotations

from difflib import SequenceMatcher
from datetime import datetime, timezone

from models import ResearchReport, StructuredFinding
from watchlist.models import DeltaFinding, WatchDelta


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _finding_key(entity: str, signal: str, signal_type: str = "") -> str:
    ent = (entity or "").strip().lower()
    st = (signal_type or "").strip().lower()
    sig = (signal or "").strip().lower()[:80]
    if ent or st or sig:
        return f"{ent}|{st or sig}"
    return sig or ent


def _from_structured(row: StructuredFinding) -> DeltaFinding:
    return DeltaFinding(
        key=_finding_key(row.entity, row.signal, row.signal_type),
        entity=row.entity,
        signal=row.signal,
        signal_type=row.signal_type or "",
        date=row.date or "",
        confidence=row.confidence or "",
        citation_index=row.citation_index or 0,
    )


def _from_fact(fact) -> DeltaFinding:
    return DeltaFinding(
        key=_finding_key("", fact.fact, getattr(fact, "signal_type", "") or ""),
        entity="",
        signal=fact.fact[:200],
        signal_type=getattr(fact, "signal_type", "") or "",
        date=getattr(fact, "event_date", "") or "",
        confidence=fact.confidence or "",
        fact=fact.fact,
        source_url=fact.source_url or "",
    )


def _extract_rows(report: ResearchReport) -> list[DeltaFinding]:
    if report.structured_findings:
        return [_from_structured(r) for r in report.structured_findings if r.signal or r.entity]
    return [_from_fact(f) for f in report.facts if f.fact]


def _index_by_key(rows: list[DeltaFinding]) -> dict[str, DeltaFinding]:
    indexed: dict[str, DeltaFinding] = {}
    for row in rows:
        key = row.key or row.signal[:80]
        # Keep first; duplicates collapse
        if key not in indexed:
            indexed[key] = row
    return indexed


def _fuzzy_match(
    row: DeltaFinding,
    candidates: dict[str, DeltaFinding],
    threshold: float = 0.82,
) -> str | None:
    best_key = None
    best = 0.0
    for key, other in candidates.items():
        score = _similarity(
            f"{row.entity} {row.signal}",
            f"{other.entity} {other.signal}",
        )
        if score > best and score >= threshold:
            best = score
            best_key = key
    return best_key


def compare_reports(
    prev: ResearchReport | None,
    curr: ResearchReport,
    *,
    watch_id: str,
    run_id: str,
) -> WatchDelta:
    """Diff structured findings (or facts) between two reports."""
    curr_rows = _extract_rows(curr)
    if prev is None:
        added = curr_rows
        delta = WatchDelta(
            watch_id=watch_id,
            run_id=run_id,
            prev_slug="",
            curr_slug=curr.slug,
            created_at=datetime.now(timezone.utc).isoformat(),
            added=added,
            removed=[],
            changed=[],
            unchanged_count=0,
        )
        delta.summary_markdown = render_delta_markdown(delta)
        return delta

    prev_rows = _extract_rows(prev)
    prev_idx = _index_by_key(prev_rows)
    curr_idx = _index_by_key(curr_rows)

    added: list[DeltaFinding] = []
    removed: list[DeltaFinding] = []
    changed: list[DeltaFinding] = []
    matched_prev: set[str] = set()
    unchanged = 0

    for key, row in curr_idx.items():
        if key in prev_idx:
            matched_prev.add(key)
            old = prev_idx[key]
            if (old.date != row.date and (old.date or row.date)) or (
                old.confidence != row.confidence and old.confidence and row.confidence
            ):
                note = []
                if old.date != row.date:
                    note.append(f"date {old.date or '—'} → {row.date or '—'}")
                if old.confidence != row.confidence:
                    note.append(f"confidence {old.confidence} → {row.confidence}")
                changed.append(row.model_copy(update={"change_note": "; ".join(note)}))
            else:
                unchanged += 1
            continue

        fuzzy = _fuzzy_match(row, {k: v for k, v in prev_idx.items() if k not in matched_prev})
        if fuzzy:
            matched_prev.add(fuzzy)
            old = prev_idx[fuzzy]
            if _similarity(old.signal, row.signal) < 0.95 or old.date != row.date:
                changed.append(row.model_copy(update={
                    "change_note": f"matched prior '{old.signal[:60]}'",
                }))
            else:
                unchanged += 1
        else:
            added.append(row)

    for key, row in prev_idx.items():
        if key not in matched_prev:
            removed.append(row)

    delta = WatchDelta(
        watch_id=watch_id,
        run_id=run_id,
        prev_slug=prev.slug,
        curr_slug=curr.slug,
        created_at=datetime.now(timezone.utc).isoformat(),
        added=added,
        removed=removed,
        changed=changed,
        unchanged_count=unchanged,
    )
    delta.summary_markdown = render_delta_markdown(delta)
    return delta


def render_delta_markdown(delta: WatchDelta) -> str:
    lines = [
        f"# Watch delta",
        "",
        f"- Previous: `{delta.prev_slug or 'none'}`",
        f"- Current: `{delta.curr_slug}`",
        f"- Added: **{len(delta.added)}** · Removed: **{len(delta.removed)}** · "
        f"Changed: **{len(delta.changed)}** · Unchanged: **{delta.unchanged_count}**",
        "",
    ]
    if delta.added:
        lines.append("## Added")
        lines.append("")
        lines.append("| Entity | Signal | Date |")
        lines.append("| --- | --- | --- |")
        for row in delta.added[:40]:
            lines.append(
                f"| {row.entity or '—'} | {(row.signal or row.fact)[:120]} | {row.date or '—'} |"
            )
        lines.append("")
    if delta.removed:
        lines.append("## Removed")
        lines.append("")
        lines.append("| Entity | Signal | Date |")
        lines.append("| --- | --- | --- |")
        for row in delta.removed[:40]:
            lines.append(
                f"| {row.entity or '—'} | {(row.signal or row.fact)[:120]} | {row.date or '—'} |"
            )
        lines.append("")
    if delta.changed:
        lines.append("## Changed")
        lines.append("")
        for row in delta.changed[:40]:
            lines.append(f"- **{row.entity or 'Finding'}**: {(row.signal or row.fact)[:160]}")
            if row.change_note:
                lines.append(f"  - _{row.change_note}_")
        lines.append("")
    if delta.curr_slug:
        lines.append(f"[Open current report](/research/{delta.curr_slug})")
    return "\n".join(lines)
