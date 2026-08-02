"""Fixed report outlines for two-pass synthesis (Wave 12c)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from models import ResearchBrief

_OUTLINES_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def load_all_outlines() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_OUTLINES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        oid = str(data.get("id") or path.stem)
        data["id"] = oid
        out[oid] = data
    return out


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
    """Map brief directions to writing slots (preferred when confirmed)."""
    slots: list[dict[str, Any]] = []
    for i, dim in enumerate(brief.dimensions):
        sid = (dim.phase_id or f"dim_{i}").strip() or f"dim_{i}"
        goal = dim.research_goal or dim.title
        detail = (dim.direction_detail or "").strip()
        writing = f"{goal}. {detail}".strip() if detail else goal
        slots.append({
            "id": sid,
            "title": dim.title,
            "title_zh": dim.title,
            "writing_goal": writing[:1200],
            "required": i < 5,
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
    return "\n".join(lines)
