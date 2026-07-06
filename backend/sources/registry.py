"""DACH source registry: intent detection and seeded site: queries."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_PATH = Path(__file__).parent / "dach_registry.yaml"


@dataclass(frozen=True)
class RegistrySource:
    id: str
    domain: str
    language: str
    category: str
    tags: tuple[str, ...]
    search_templates: tuple[str, ...]


def _load_raw() -> dict[str, Any]:
    if not _REGISTRY_PATH.is_file():
        return {"intent_keywords": {}, "sources": []}
    data = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def load_sources() -> list[RegistrySource]:
    raw_sources = _load_raw().get("sources") or []
    sources: list[RegistrySource] = []
    for item in raw_sources:
        if not isinstance(item, dict) or not item.get("domain"):
            continue
        templates = item.get("search_templates") or []
        sources.append(
            RegistrySource(
                id=str(item.get("id") or item["domain"]),
                domain=str(item["domain"]),
                language=str(item.get("language") or "en"),
                category=str(item.get("category") or "media"),
                tags=tuple(item.get("tags") or []),
                search_templates=tuple(str(t) for t in templates if t),
            )
        )
    return sources


@lru_cache(maxsize=1)
def _intent_keywords() -> dict[str, tuple[str, ...]]:
    raw = _load_raw().get("intent_keywords") or {}
    return {
        group: tuple(str(k).lower() for k in keywords if k)
        for group, keywords in raw.items()
        if isinstance(keywords, list)
    }


def _topic_lower(topic: str) -> str:
    return topic.lower().strip()


def _matches_any(topic: str, keywords: tuple[str, ...]) -> bool:
    t = _topic_lower(topic)
    return any(k in t for k in keywords)


def dach_intent_score(topic: str) -> int:
    """Higher score = stronger DACH/narrow-domain intent."""
    groups = _intent_keywords()
    score = 0
    if _matches_any(topic, groups.get("geo", ())):
        score += 3
    if _matches_any(topic, groups.get("venture", ())):
        score += 2
    if _matches_any(topic, groups.get("sectors", ())):
        score += 1
    return score


def has_dach_intent(topic: str, min_score: int = 2) -> bool:
    """True when topic targets Swiss/DACH startup or PE intelligence."""
    return dach_intent_score(topic) >= min_score


def _rank_sources(topic: str) -> list[RegistrySource]:
    groups = _intent_keywords()
    geo = _matches_any(topic, groups.get("geo", ()))
    venture = _matches_any(topic, groups.get("venture", ()))
    sector = _matches_any(topic, groups.get("sectors", ()))

    def source_score(source: RegistrySource) -> int:
        score = 0
        if geo and "geo" in source.tags:
            score += 3
        if venture and "venture" in source.tags:
            score += 2
        if sector and "sectors" in source.tags:
            score += 1
        if source.category in ("media", "university"):
            score += 1
        return score

    ranked = sorted(load_sources(), key=source_score, reverse=True)
    return [s for s in ranked if source_score(s) > 0] or ranked


def _compact_topic(topic: str, max_words: int = 8) -> str:
    words = topic.split()
    if len(words) <= max_words:
        return topic.strip()
    return " ".join(words[:max_words])


def build_seed_queries(topic: str, max_seeds: int = 5) -> list[str]:
    """Build deterministic site: seed queries from the registry."""
    if not has_dach_intent(topic):
        return []

    compact = _compact_topic(topic)
    seeds: list[str] = []
    seen: set[str] = set()

    for source in _rank_sources(topic):
        for template in source.search_templates:
            query = template.replace("{topic}", compact).strip()
            if not query or query in seen:
                continue
            seen.add(query)
            seeds.append(query)
            if len(seeds) >= max_seeds:
                return seeds
    return seeds


def augment_queries(topic: str, queries: list[str], max_extra: int = 2) -> list[str]:
    """Append a few registry seeds to planner/deep dimension queries."""
    extra = build_seed_queries(topic, max_seeds=max_extra)
    merged: list[str] = []
    seen: set[str] = set()
    for q in [*queries, *extra]:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            merged.append(q)
    return merged


def clear_registry_cache() -> None:
    """Clear cached YAML (for tests)."""
    load_sources.cache_clear()
    _intent_keywords.cache_clear()
