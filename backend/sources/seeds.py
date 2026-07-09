"""Combined DACH + private debt seed query builder."""

from __future__ import annotations

from sources.pd_registry import (
    build_pd_seed_queries,
    has_private_debt_intent,
    private_debt_intent_score,
)
from sources.registry import (
    augment_queries as augment_dach_queries,
    build_seed_queries as build_dach_seed_queries,
    dach_intent_score,
    has_dach_intent,
)


def has_registry_intent(topic: str) -> bool:
    """True when topic matches DACH venture or private debt registry."""
    return has_dach_intent(topic) or has_private_debt_intent(topic)


def build_combined_seed_queries(topic: str, max_seeds: int = 5) -> list[str]:
    """Merge DACH and private debt site: seeds, deduplicated."""
    if not has_registry_intent(topic):
        return []

    # Split budget: PD topics prioritize PD seeds
    if has_private_debt_intent(topic) and not has_dach_intent(topic):
        pd_budget = max_seeds
        dach_budget = 0
    elif has_dach_intent(topic) and not has_private_debt_intent(topic):
        pd_budget = 0
        dach_budget = max_seeds
    else:
        pd_budget = max(max_seeds // 2, 2)
        dach_budget = max_seeds - pd_budget

    seeds: list[str] = []
    seen: set[str] = set()
    for q in [
        *build_pd_seed_queries(topic, max_seeds=pd_budget),
        *build_dach_seed_queries(topic, max_seeds=dach_budget),
    ]:
        if q not in seen:
            seen.add(q)
            seeds.append(q)
    return seeds[:max_seeds]


def augment_queries(topic: str, queries: list[str], max_extra: int = 2) -> list[str]:
    """Append registry seeds (DACH + private debt) to dimension queries."""
    extra = build_combined_seed_queries(topic, max_seeds=max_extra)
    merged: list[str] = []
    seen: set[str] = set()
    for q in [*queries, *extra]:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            merged.append(q)
    return merged


def registry_intent_label(topic: str) -> str | None:
    """Human-readable intent for SSE / logging."""
    pd = private_debt_intent_score(topic)
    dach = dach_intent_score(topic)
    if pd >= 3 and dach >= 2:
        return "private_debt+dach"
    if pd >= 3:
        return "private_debt"
    if dach >= 2:
        return "dach"
    return None
