"""DACH narrow-domain source registry (Phase 1)."""
from sources.registry import (
    augment_queries,
    build_seed_queries,
    dach_intent_score,
    has_dach_intent,
    load_sources,
)

__all__ = [
    "augment_queries",
    "build_seed_queries",
    "dach_intent_score",
    "has_dach_intent",
    "load_sources",
]
