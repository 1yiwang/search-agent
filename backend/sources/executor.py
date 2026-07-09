"""Deterministic search executor for Source Router decisions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from config import config
from dedup import deduplicate_search_results, normalize_url
from models import SearchResult
from search import fetch_page, search_and_fetch, search_web
from sources.models import RouterDecision
from sources.seeds import has_registry_intent

FetchEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def _domain_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


async def _direct_fetch_urls(
    urls: list[str],
    seen_urls: set[str],
    event_callback: FetchEventCallback | None,
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for url in urls:
        norm = normalize_url(url)
        if norm in seen_urls:
            continue
        text = await fetch_page(url, event_callback=event_callback)
        seen_urls.add(norm)
        title = url.rsplit("/", 1)[-1] or url
        results.append(SearchResult(
            url=url,
            title=title,
            snippet=text[:300] if text else "",
            full_text=text,
        ))
        if event_callback:
            await event_callback("direct_fetch", {"url": url, "chars": len(text or "")})
    return results


async def _site_searches(
    queries: list[str],
    seen_urls: set[str],
    event_callback: FetchEventCallback | None,
    recency_days: int | None,
    max_per_query: int,
) -> list[SearchResult]:
    all_results: list[SearchResult] = []
    for query in queries:
        hits = await search_and_fetch(
            query,
            max_per_query,
            event_callback=event_callback,
            days=recency_days,
        )
        for hit in hits:
            if normalize_url(hit.url) not in seen_urls:
                all_results.append(hit)
    return all_results


async def execute_router_decision(
    topic: str,
    decision: RouterDecision,
    seen_urls: set[str],
    *,
    budget_remaining: int,
    event_callback: FetchEventCallback | None = None,
    force_open_web: bool = False,
) -> tuple[list[SearchResult], list[str]]:
    """Run direct_fetch → site_search → optional open_search."""
    topics_searched: list[str] = []
    recency_days = config.research_recency_days if has_registry_intent(topic) else None
    max_per_query = max(2, min(config.dach_seed_results_per_query, budget_remaining))

    collected: list[SearchResult] = []

    if decision.direct_url_fetches:
        direct = await _direct_fetch_urls(
            decision.direct_url_fetches[: config.router_max_direct_fetches],
            seen_urls,
            event_callback,
        )
        for r in direct:
            seen_urls.add(normalize_url(r.url))
        collected.extend(direct)

    if decision.site_queries and len(collected) < budget_remaining:
        topics_searched.extend(decision.site_queries)
        site_hits = await _site_searches(
            decision.site_queries,
            seen_urls,
            event_callback,
            recency_days,
            max_per_query,
        )
        for r in site_hits:
            seen_urls.add(normalize_url(r.url))
        collected.extend(site_hits)

    unique_domains = len({_domain_from_url(r.url) for r in collected if r.url})
    need_open = (
        force_open_web
        or unique_domains < 2
        or (not decision.defer_open_web and len(collected) < max(3, budget_remaining // 2))
    )
    if need_open and len(collected) < budget_remaining:
        open_budget = budget_remaining - len(collected)
        topics_searched.append(topic)
        open_hits = await search_and_fetch(
            topic,
            min(open_budget, config.search_max_results),
            event_callback=event_callback,
            days=recency_days,
        )
        for r in open_hits:
            norm = normalize_url(r.url)
            if norm not in seen_urls:
                seen_urls.add(norm)
                collected.append(r)

    unique = deduplicate_search_results(collected)
    return unique[:budget_remaining], topics_searched
