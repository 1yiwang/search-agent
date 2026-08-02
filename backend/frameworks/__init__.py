"""Load and select industry research framework skeletons (Wave 12a)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from report_synthesis import detect_report_type
from sources.telecom_intent import has_swiss_telecom_intent, telecom_intent_score

_FRAMEWORKS_DIR = Path(__file__).resolve().parent
_frameworks_cache: dict[str, dict[str, Any]] | None = None
_frameworks_cache_key: tuple[tuple[str, float], ...] | None = None


def _frameworks_mtime_key() -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted(
            (p.name, p.stat().st_mtime)
            for p in _FRAMEWORKS_DIR.glob("*.yaml")
        )
    )


def load_all_frameworks() -> dict[str, dict[str, Any]]:
    global _frameworks_cache, _frameworks_cache_key
    key = _frameworks_mtime_key()
    if _frameworks_cache is not None and _frameworks_cache_key == key:
        return _frameworks_cache
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_FRAMEWORKS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        fid = str(data.get("id") or path.stem)
        data["id"] = fid
        out[fid] = data
    _frameworks_cache = out
    _frameworks_cache_key = key
    return out


def clear_frameworks_cache() -> None:
    global _frameworks_cache, _frameworks_cache_key
    _frameworks_cache = None
    _frameworks_cache_key = None


def get_framework(framework_id: str) -> dict[str, Any]:
    frameworks = load_all_frameworks()
    if framework_id not in frameworks:
        raise KeyError(f"Unknown framework: {framework_id}")
    return frameworks[framework_id]


_ENTRY_MARKERS = (
    "market entry", "enter the", "entering", "opportunity", "opportunit",
    "expansion", "expand into", "go-to-market", "gtm",
    "进入", "市场进入", "商机", "机会", "拓展", "出海", "落地",
)
_COMPETITIVE_MARKERS = (
    "competitive landscape", "competitor", "competitors", "vs ", " versus ",
    "market share ranking", "竞品", "竞争格局", "市占", "对比",
)


def select_framework_id(topic: str) -> str:
    """Deterministic framework picker (no LLM)."""
    t = topic.lower()
    if detect_report_type(topic) == "investor_brief":
        return "investor_brief"
    if has_swiss_telecom_intent(topic) or telecom_intent_score(topic) >= 3:
        return "market_entry"
    if any(m in t or m in topic for m in _ENTRY_MARKERS):
        return "market_entry"
    if any(m in t or m in topic for m in _COMPETITIVE_MARKERS):
        return "competitive_landscape"
    return "general_industry"


def framework_prompt_block(framework_id: str) -> str:
    """Serialize skeleton as Chinese coverage angles — never English titles/goals."""
    fw = get_framework(framework_id)
    lines = [
        f"Checklist id: {fw.get('id')}",
        f"Purpose: {fw.get('description', '')}",
        "必须覆盖的角度（只参考 angle_id + 中文提示；禁止把英文标签粘贴进计划）：",
    ]
    for i, phase in enumerate(fw.get("phases") or [], 1):
        cover = (
            str(phase.get("cover_zh") or "").strip()
            or str(phase.get("id") or "").replace("_", " ")
        )
        lines.append(f"  {i}. angle_id={phase.get('id')} — {cover}")
    deps = fw.get("default_deprioritize") or []
    if deps:
        lines.append("默认降权（不要主动研究）：")
        for d in deps:
            lines.append(f"  - {d}")
    rules = (fw.get("prompt_rules") or "").strip()
    if rules:
        lines.append("Rules:")
        lines.append(rules)
    return "\n".join(lines)


def framework_forbidden_phrases(framework_id: str) -> set[str]:
    """English titles/goals that must never appear in user-facing plan text."""
    fw = get_framework(framework_id)
    out: set[str] = set()
    for phase in fw.get("phases") or []:
        for key in ("title", "goal"):
            val = str(phase.get(key) or "").strip().lower()
            if len(val) >= 8:
                out.add(val)
    return out
