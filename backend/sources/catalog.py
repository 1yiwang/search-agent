"""Unified source catalog: load, filter, serialize for Source Router."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from sources.models import SourceEntry
from sources.pd_registry import has_private_debt_intent, private_debt_intent_score
from sources.registry import dach_intent_score

_CATALOG_DIR = Path(__file__).parent / "catalog"
_LINKS_PATH = Path(__file__).parent / "links" / "private_debt_seed_urls.yaml"


def _parse_source(item: dict[str, Any]) -> SourceEntry | None:
    if not isinstance(item, dict) or not item.get("id") or not item.get("domain"):
        return None
    return SourceEntry(
        id=str(item["id"]),
        name=str(item.get("name") or item["id"]),
        domain=str(item["domain"]),
        language=str(item.get("language") or "en"),
        category=str(item.get("category") or "media"),
        tags=[str(t) for t in (item.get("tags") or [])],
        trust_tier=str(item.get("trust_tier") or "secondary"),
        access_modes=[str(m) for m in (item.get("access_modes") or ["site_search"])],
        search_templates=[str(t) for t in (item.get("search_templates") or []) if t],
        entry_urls=[str(u) for u in (item.get("entry_urls") or []) if u],
        notes=str(item.get("notes") or ""),
    )


@lru_cache(maxsize=1)
def load_catalog() -> list[SourceEntry]:
    """Load all sources from catalog/*.yaml (excluding _schema)."""
    sources: list[SourceEntry] = []
    seen_ids: set[str] = set()
    if not _CATALOG_DIR.is_dir():
        return sources

    for path in sorted(_CATALOG_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for item in data.get("sources") or []:
            entry = _parse_source(item)
            if entry and entry.id not in seen_ids:
                seen_ids.add(entry.id)
                sources.append(entry)

    _merge_link_urls(sources)
    return sources


def _merge_link_urls(sources: list[SourceEntry]) -> None:
    """Append curated direct URLs from links/*.yaml into matching catalog entries."""
    if not _LINKS_PATH.is_file():
        return
    data = yaml.safe_load(_LINKS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    by_id = {s.id: s for s in sources}
    for item in data.get("urls") or []:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("source_id") or "")
        url = str(item.get("url") or "").strip()
        if sid in by_id and url and url not in by_id[sid].entry_urls:
            by_id[sid].entry_urls.append(url)
            if "direct_urls" not in by_id[sid].access_modes:
                by_id[sid].access_modes.append("direct_urls")


def get_source_by_id(source_id: str) -> SourceEntry | None:
    for entry in load_catalog():
        if entry.id == source_id:
            return entry
    return None


def _topic_lower(topic: str) -> str:
    return topic.lower().strip()


def _score_source_for_topic(entry: SourceEntry, topic: str) -> int:
    t = _topic_lower(topic)
    score = 0
    pd = has_private_debt_intent(topic)
    dach = has_dach_intent(topic)

    tag_set = set(entry.tags)
    if pd and "credit" in tag_set:
        score += 4
    if dach and "venture" in tag_set:
        score += 3
    if (pd or dach) and "geo" in tag_set:
        score += 2
    if "regulatory" in tag_set and (pd or "regulatory" in t or "finma" in t):
        score += 2
    if entry.trust_tier == "primary":
        score += 2
    if entry.category == "research":
        score += 2
    if entry.entry_urls:
        score += 1
    return score


def filter_candidates(topic: str, max_candidates: int = 25) -> list[SourceEntry]:
    """Deterministic pre-filter before LLM Source Router.

    General topics (including bare «European …» without venture/credit intent)
    return an empty catalog so the loop runs open-web first.
    """
    catalog = load_catalog()
    if not catalog:
        return []

    pd = has_private_debt_intent(topic)
    # geo alone (e.g. "European AI…") is score 3; require geo+venture (≥5) for DACH catalog.
    dach_strong = dach_intent_score(topic) >= 5
    if not pd and not dach_strong:
        return []

    ranked = sorted(catalog, key=lambda e: _score_source_for_topic(e, topic), reverse=True)
    positive = [e for e in ranked if _score_source_for_topic(e, topic) > 0]
    return (positive or ranked)[:max_candidates]


def intent_labels(topic: str) -> list[str]:
    labels: list[str] = []
    if private_debt_intent_score(topic) >= 3:
        labels.append("private_debt")
    if dach_intent_score(topic) >= 2:
        labels.append("dach_venture")
    return labels or ["general"]


def catalog_summary_for_llm(candidates: list[SourceEntry]) -> list[dict[str, Any]]:
    """Compact catalog rows for router prompt."""
    return [
        {
            "id": e.id,
            "name": e.name,
            "domain": e.domain,
            "category": e.category,
            "tags": e.tags,
            "trust_tier": e.trust_tier,
            "notes": e.notes,
            "has_entry_urls": bool(e.entry_urls),
            "sample_templates": e.search_templates[:2],
        }
        for e in candidates
    ]


def clear_catalog_cache() -> None:
    load_catalog.cache_clear()
