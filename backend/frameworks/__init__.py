"""Load and select industry research framework skeletons (Wave 12a)."""

from __future__ import annotations

import re
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


_EXAMPLES_DIR = _FRAMEWORKS_DIR / "examples"
_examples_cache: dict[str, dict[str, Any]] | None = None
_examples_cache_key: tuple[tuple[str, float], ...] | None = None


def _examples_mtime_key() -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted(
            (p.name, p.stat().st_mtime)
            for p in _EXAMPLES_DIR.glob("*.yaml")
        )
    )


def load_all_examples() -> dict[str, dict[str, Any]]:
    """Few-shot plan examples (Wave 12h Step 87) — no domain templates in code."""
    global _examples_cache, _examples_cache_key
    if not _EXAMPLES_DIR.is_dir():
        return {}
    key = _examples_mtime_key()
    if _examples_cache is not None and _examples_cache_key == key:
        return _examples_cache
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_EXAMPLES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        eid = str(data.get("id") or path.stem)
        data["id"] = eid
        out[eid] = data
    _examples_cache = out
    _examples_cache_key = key
    return out


def clear_examples_cache() -> None:
    global _examples_cache, _examples_cache_key
    _examples_cache = None
    _examples_cache_key = None


def _topic_language(topic: str) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", topic or "") else "en"


def _example_matches(example: dict[str, Any], topic: str) -> bool:
    lang = str(example.get("language") or "").strip()
    if lang and lang != _topic_language(topic):
        return False
    groups = example.get("match") or []
    if not groups:
        return False
    low = (topic or "").lower()
    for group in groups:
        if not any(str(kw).lower() in low for kw in (group or [])):
            return False
    return True


def select_example(topic: str) -> dict[str, Any] | None:
    """Best-matching example for a topic (all keyword groups must hit)."""
    for example in load_all_examples().values():
        if _example_matches(example, topic):
            return example
    return None


def _gold_standard_example() -> dict[str, Any] | None:
    examples = load_all_examples()
    for example in examples.values():
        if example.get("gold_standard"):
            return example
    return next(iter(examples.values()), None)


def example_instruction(topic: str, phase_id: str) -> str | None:
    """Example instruction for a phase when the LLM output must be replaced."""
    example = select_example(topic)
    if not example:
        return None
    for direction in example.get("directions") or []:
        if str(direction.get("phase_id") or "") != phase_id:
            continue
        detail = str(direction.get("detail") or "").strip()
        if detail:
            return detail.replace("{topic}", topic)
    return None


def example_seed_queries(topic: str) -> list[str]:
    """Entity-rich seed queries from the matching example, if any."""
    example = select_example(topic)
    if not example:
        return []
    return [
        str(q).strip().replace("{topic}", topic)
        for q in (example.get("seed_queries") or [])
        if str(q).strip()
    ]


def few_shot_block(topic: str, *, max_directions: int = 6) -> str:
    """Numbered gold-standard plan injected into the brief system prompt."""
    example = select_example(topic) or _gold_standard_example()
    if not example:
        return ""
    directions = (example.get("directions") or [])[:max_directions]
    if not directions:
        return ""
    lines = [f"选题：{example.get('topic_example') or topic}"]
    for i, direction in enumerate(directions, 1):
        detail = str(direction.get("detail") or "").strip().replace("{topic}", topic)
        if detail:
            lines.append(f"({i}) {detail}")
    return "\n".join(lines)


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
