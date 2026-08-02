"""Fixed report outlines for two-pass synthesis (Wave 12c)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from models import ResearchBrief

_OUTLINES_DIR = Path(__file__).resolve().parent
_outlines_cache: dict[str, dict[str, Any]] | None = None
_outlines_cache_key: tuple[tuple[str, float], ...] | None = None


def _outlines_mtime_key() -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted(
            (p.name, p.stat().st_mtime)
            for p in _OUTLINES_DIR.glob("*.yaml")
        )
    )


def load_all_outlines() -> dict[str, dict[str, Any]]:
    global _outlines_cache, _outlines_cache_key
    key = _outlines_mtime_key()
    if _outlines_cache is not None and _outlines_cache_key == key:
        return _outlines_cache
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_OUTLINES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        oid = str(data.get("id") or path.stem)
        data["id"] = oid
        out[oid] = data
    _outlines_cache = out
    _outlines_cache_key = key
    return out


def clear_outlines_cache() -> None:
    global _outlines_cache, _outlines_cache_key
    _outlines_cache = None
    _outlines_cache_key = None


def get_outline(outline_id: str) -> dict[str, Any]:
    outlines = load_all_outlines()
    if outline_id not in outlines:
        return outlines.get("general_industry") or next(iter(outlines.values()))
    return outlines[outline_id]


def select_outline_id(topic: str, brief: ResearchBrief | None = None) -> str:
    """Pick outline: approved brief framework → else same rules as frameworks."""
    if brief and brief.framework_id:
        fid = brief.framework_id
        if fid in load_all_outlines():
            return fid
    # Lazy import avoids frameworks ↔ report_synthesis cycles
    from frameworks import select_framework_id
    return select_framework_id(topic)


def slots_from_outline(outline: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in (outline.get("slots") or []) if isinstance(s, dict) and s.get("id")]


def slots_from_brief(brief: ResearchBrief) -> list[dict[str, Any]]:
    """Map brief directions to writing slots 1:1 — every approved direction is a section."""
    slots: list[dict[str, Any]] = []
    for i, dim in enumerate(brief.dimensions):
        sid = (dim.direction_id or dim.phase_id or f"dim_{i}").strip() or f"dim_{i}"
        goal = (dim.research_goal or "").strip()
        detail = (dim.direction_detail or "").strip()
        parts = [p for p in (detail, goal) if p]
        # goal often mirrors detail — repeating it empties the writing contract
        if len(parts) == 2 and parts[0] == parts[1]:
            parts = parts[:1]
        if not parts:
            parts = [dim.title]
        if dim.must_answer:
            parts.append("必须回答：" + "；".join(dim.must_answer[:3]))
        slots.append({
            "id": sid,
            "title": dim.title,
            "title_zh": dim.title,
            "writing_goal": " ".join(parts)[:1200],
            "must_answer": list(dim.must_answer or [])[:3],
            "entities": list(dim.entities or [])[:6],
            "required": True,
        })
    return slots


def resolve_slots(
    topic: str,
    brief: ResearchBrief | None = None,
) -> tuple[str, list[dict[str, Any]], str]:
    """Return (outline_id, slots, deprioritize_hint)."""
    if brief and brief.dimensions:
        oid = brief.framework_id or select_outline_id(topic, brief)
        outline = get_outline(oid) if oid in load_all_outlines() else {}
        hint = str(outline.get("deprioritize_hint") or "")
        deps = list(brief.deprioritize or [])
        if hint and hint not in deps:
            deps.append(hint)
        return oid, slots_from_brief(brief), "; ".join(deps) if deps else hint

    oid = select_outline_id(topic, brief)
    outline = get_outline(oid)
    return oid, slots_from_outline(outline), str(outline.get("deprioritize_hint") or "")


def outline_prompt_block(slots: list[dict[str, Any]], *, zh: bool = False) -> str:
    lines = ["Fixed report slots (assign facts into these only):"]
    for i, slot in enumerate(slots, 1):
        title = slot.get("title_zh") if zh and slot.get("title_zh") else slot.get("title")
        req = "required" if slot.get("required") else "optional"
        lines.append(
            f"  {i}. [{slot.get('id')}] {title} ({req}): {slot.get('writing_goal', '')}"
        )
        must = slot.get("must_answer") or []
        if must:
            lines.append(f"     must_answer: {'; '.join(str(m) for m in must)}")
    return "\n".join(lines)
