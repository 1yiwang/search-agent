"""Deterministic search executor for Source Router decisions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

from config import config
from dedup import deduplicate_search_results, normalize_url
from models import SearchResult
from query_expand import (
    alternate_entry_urls,
    alternate_site_queries,
    alternate_source_entry_urls,
)
from search import fetch_page, search_and_fetch
from sources.models import RouterDecision
from sources.seeds import has_registry_intent

FetchEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def _domain_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


@contextmanager
def _tavily_depth_override(depth: str):
    original = config.tavily_search_depth
    config.tavily_search_depth = depth
    try:
        yield
    finally:
        config.tavily_search_depth = original


class _nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


async def _direct_fetch_urls(
    urls: list[str],
    seen_urls: set[str],
    event_callback: FetchEventCallback | None,
    *,
    missing_dimensions: list[str] | None = None,
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for url in urls:
        norm = normalize_url(url)
        if norm in seen_urls:
            continue
        text = await fetch_page(url, event_callback=event_callback)
        final_url = url

        if text.startswith("[Failed"):
            retry_candidates = list(alternate_entry_urls(url))
            retry_candidates.extend(
                u for u in alternate_source_entry_urls(
                    url, missing_dimensions=missing_dimensions,
                )
                if u not in retry_candidates
            )
            for alt in retry_candidates:
                alt_norm = normalize_url(alt)
                if alt_norm in seen_urls:
                    continue
                retry_text = await fetch_page(alt, event_callback=event_callback)
                if not retry_text.startswith("[Failed"):
                    if event_callback:
                        same_host = _domain_from_url(url) == _domain_from_url(alt)
                        await event_callback(
                            "fetch_retry" if same_host else "fetch_failover",
                            {"from": url, "to": alt},
                        )
                    final_url = alt
                    text = retry_text
                    seen_urls.add(alt_norm)
                    break

        seen_urls.add(normalize_url(final_url))
        title = final_url.rsplit("/", 1)[-1] or final_url
        results.append(SearchResult(
            url=final_url,
            title=title,
            snippet=text[:300] if text else "",
            full_text=text,
        ))
        if event_callback:
            await event_callback("direct_fetch", {"url": final_url, "chars": len(text or "")})
    return results


async def _site_searches(
    queries: list[str],
    seen_urls: set[str],
    event_callback: FetchEventCallback | None,
    recency_days: int | None,
    max_per_query: int,
    *,
    topic: str = "",
    missing_dimensions: list[str] | None = None,
    gap_hop: bool = False,
) -> tuple[list[SearchResult], list[str]]:
    """Run site: searches; on empty hits, try alternate catalog domains."""
    all_results: list[SearchResult] = []
    searched: list[str] = []
    depth_ctx = (
        _tavily_depth_override("advanced")
        if gap_hop and config.tavily_deep_on_gap_hop
        else _nullcontext()
    )
    with depth_ctx:
        for query in queries:
            searched.append(query)
            hits = await search_and_fetch(
                query,
                max_per_query,
                event_callback=event_callback,
                days=recency_days,
            )
            new_hits = [
                h for h in hits if normalize_url(h.url) not in seen_urls
            ]
            if not new_hits and topic:
                for alt_q in alternate_site_queries(
                    query,
                    topic,
                    missing_dimensions=missing_dimensions,
                ):
                    if event_callback:
                        await event_callback("site_search_failover", {
                            "from": query,
                            "to": alt_q,
                        })
                    searched.append(alt_q)
                    alt_hits = await search_and_fetch(
                        alt_q,
                        max_per_query,
                        event_callback=event_callback,
                        days=recency_days,
                    )
                    new_hits = [
                        h for h in alt_hits
                        if normalize_url(h.url) not in seen_urls
                    ]
                    if new_hits:
                        break
            for hit in new_hits:
                seen_urls.add(normalize_url(hit.url))
                all_results.append(hit)
    return all_results, searched


async def execute_router_decision(
    topic: str,
    decision: RouterDecision,
    seen_urls: set[str],
    *,
    budget_remaining: int,
    event_callback: FetchEventCallback | None = None,
    force_open_web: bool = False,
    open_queries: list[str] | None = None,
    missing_dimensions: list[str] | None = None,
    gap_hop: bool = False,
) -> tuple[list[SearchResult], list[str]]:
    """Run direct_fetch → site_search → optional open_search."""
    topics_searched: list[str] = []
    recency_days = config.research_recency_days if has_registry_intent(topic) else None
    open_budget_reserved = max(2, budget_remaining // 3)
    site_budget = max(0, budget_remaining - open_budget_reserved)
    max_per_query = max(2, min(config.dach_seed_results_per_query, site_budget or budget_remaining))

    collected: list[SearchResult] = []

    if decision.direct_url_fetches and site_budget > 0:
        direct = await _direct_fetch_urls(
            decision.direct_url_fetches[: config.router_max_direct_fetches],
            seen_urls,
            event_callback,
            missing_dimensions=missing_dimensions,
        )
        for r in direct:
            seen_urls.add(normalize_url(r.url))
        collected.extend(direct)

    if decision.site_queries and len(collected) < site_budget:
        site_hits, site_searched = await _site_searches(
            decision.site_queries,
            seen_urls,
            event_callback,
            recency_days,
            max_per_query,
            topic=topic,
            missing_dimensions=missing_dimensions,
            gap_hop=gap_hop,
        )
        topics_searched.extend(site_searched)
        for r in site_hits:
            seen_urls.add(normalize_url(r.url))
        collected.extend(site_hits[: max(0, site_budget - len(collected))])

    unique_domains = len({_domain_from_url(r.url) for r in collected if r.url})
    has_gaps = bool(missing_dimensions)
    diversity_low = unique_domains < config.min_unique_domains_target
    need_open = (
        force_open_web
        or diversity_low
        or has_gaps
        or bool(open_queries)
        or (not decision.defer_open_web and len(collected) < max(3, budget_remaining // 2))
    )
    if need_open and len(collected) < budget_remaining:
        if event_callback and (diversity_low or has_gaps) and decision.defer_open_web:
            await event_callback("open_search_forced", {
                "reason": "gaps" if has_gaps else "low_diversity",
                "unique_domains": unique_domains,
                "missing_dimensions": missing_dimensions or [],
            })
        open_budget = min(
            max(open_budget_reserved, budget_remaining - len(collected)),
            budget_remaining - len(collected),
        )
        queries_to_run = open_queries or [topic]
        # Budget-aware open query count: ≥2 when possible, ≤4, scales with budget.
        max_open_queries = min(
            len(queries_to_run),
            max(1, min(4, max(2, open_budget // 2))),
        )
        queries_slice = queries_to_run[:max_open_queries]
        per_query = max(1, open_budget // max(1, len(queries_slice)))
        for open_query in queries_slice:
            if len(collected) >= budget_remaining:
                break
            topics_searched.append(open_query)
            depth_ctx = (
                _tavily_depth_override("advanced")
                if gap_hop and config.tavily_deep_on_gap_hop
                else _nullcontext()
            )
            with depth_ctx:
                open_hits = await search_and_fetch(
                    open_query,
                    min(per_query, config.search_max_results),
                    event_callback=event_callback,
                    days=recency_days,
                )
            for r in open_hits:
                norm = normalize_url(r.url)
                if norm not in seen_urls:
                    seen_urls.add(norm)
                    collected.append(r)
                    if len(collected) >= budget_remaining:
                        break

    unique = deduplicate_search_results(collected)
    return unique[:budget_remaining], topics_searched
