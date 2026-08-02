"""Load and select industry research framework skeletons (Wave 12a)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from report_synthesis import detect_report_type
from sources.telecom_intent import has_swiss_telecom_intent, telecom_intent_score

_FRAMEWORKS_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def load_all_frameworks() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_FRAMEWORKS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        fid = str(data.get("id") or path.stem)
        data["id"] = fid
        out[fid] = data
    return out


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
    """Serialize skeleton as a coverage checklist (not titles to copy)."""
    fw = get_framework(framework_id)
    lines = [
        f"Checklist id: {fw.get('id')}",
        f"Purpose: {fw.get('description', '')}",
        "Angles to COVER (rewrite each as a topic-specific instruction — do not copy titles):",
    ]
    for i, phase in enumerate(fw.get("phases") or [], 1):
        lines.append(
            f"  {i}. angle_id={phase.get('id')} — cover: {phase.get('goal')}"
        )
    deps = fw.get("default_deprioritize") or []
    if deps:
        lines.append("Default deprioritize:")
        for d in deps:
            lines.append(f"  - {d}")
    rules = (fw.get("prompt_rules") or "").strip()
    if rules:
        lines.append("Rules:")
        lines.append(rules)
    return "\n".join(lines)
