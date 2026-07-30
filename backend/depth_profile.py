"""Research depth profiles (Wave 10 Step 62).

Maps fast | standard | deep → source budget, hops, open fan-out, fetch top-K.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

from config import config
from models import ResearchRequest

DepthName = Literal["fast", "standard", "deep"]


@dataclass(frozen=True)
class DepthProfile:
    name: DepthName
    max_sources: int
    max_hops: int
    max_router_calls: int
    open_max_queries: int
    fetch_top_k: int
    expand_max: int
    label: str


DEPTH_PROFILES: dict[str, DepthProfile] = {
    "fast": DepthProfile(
        name="fast",
        max_sources=8,
        max_hops=2,
        max_router_calls=2,
        open_max_queries=3,
        fetch_top_k=6,
        expand_max=4,
        label="Fast",
    ),
    "standard": DepthProfile(
        name="standard",
        max_sources=15,
        max_hops=4,
        max_router_calls=3,
        open_max_queries=5,
        fetch_top_k=10,
        expand_max=6,
        label="Standard",
    ),
    "deep": DepthProfile(
        name="deep",
        max_sources=20,
        max_hops=5,
        max_router_calls=4,
        open_max_queries=6,
        fetch_top_k=12,
        expand_max=8,
        label="Deep",
    ),
}


def get_depth_profile(depth: str | None) -> DepthProfile:
    key = (depth or "standard").strip().lower()
    return DEPTH_PROFILES.get(key, DEPTH_PROFILES["standard"])


def resolve_request(request: ResearchRequest) -> tuple[ResearchRequest, DepthProfile]:
    """Apply depth profile to max_sources (and return profile for hop overrides)."""
    profile = get_depth_profile(getattr(request, "depth", None) or "standard")
    # Depth profile owns budget unless caller set a non-default max_sources with no depth
    # Prefer explicit depth → profile.max_sources.
    updated = request.model_copy(update={"max_sources": profile.max_sources, "depth": profile.name})
    return updated, profile


@contextmanager
def depth_overrides(profile: DepthProfile) -> Iterator[DepthProfile]:
    """Temporarily apply hop / open / fetch knobs for one research run."""
    originals = {
        "research_max_hops": config.research_max_hops,
        "research_max_router_calls": config.research_max_router_calls,
        "open_max_queries_per_hop": config.open_max_queries_per_hop,
        "fetch_top_k_per_hop": config.fetch_top_k_per_hop,
        "query_expand_max_per_hop": config.query_expand_max_per_hop,
    }
    config.research_max_hops = profile.max_hops
    config.research_max_router_calls = profile.max_router_calls
    config.open_max_queries_per_hop = profile.open_max_queries
    config.fetch_top_k_per_hop = profile.fetch_top_k
    config.query_expand_max_per_hop = profile.expand_max
    try:
        yield profile
    finally:
        config.research_max_hops = originals["research_max_hops"]
        config.research_max_router_calls = originals["research_max_router_calls"]
        config.open_max_queries_per_hop = originals["open_max_queries_per_hop"]
        config.fetch_top_k_per_hop = originals["fetch_top_k_per_hop"]
        config.query_expand_max_per_hop = originals["query_expand_max_per_hop"]
