"""Web search and page fetching module (facade over providers)."""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from config import config
from dedup import deduplicate_search_results
from models import SearchResult
from providers import get_fetch_provider, get_search_provider
from providers.fetch_chain import ChainedFetchProvider
from sources.registry import build_seed_queries, has_dach_intent

FetchEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


async def search_web(
    query: str,
    max_results: int = None,
    *,
    days: int | None = None,
    include_domains: list[str] | None = None,
) -> list[SearchResult]:
    """Search the web using the configured search provider."""
    if max_results is None:
        max_results = config.search_max_results
    provider = get_search_provider()
    if hasattr(provider, "search"):
        try:
            return await provider.search(
                query,
                max_results,
                days=days,
                include_domains=include_domains,
            )
        except TypeError:
            return await provider.search(query, max_results)
    return await provider.search(query, max_results)


async def fetch_page(
    url: str,
    timeout: int = 15,
    event_callback: FetchEventCallback | None = None,
) -> str:
    """Fetch a webpage using the configured fetch provider."""
    provider = get_fetch_provider()
    if isinstance(provider, ChainedFetchProvider):
        text, _ = await provider.fetch_with_meta(url, timeout=timeout, event_callback=event_callback)
        return text
    return await provider.fetch(url, timeout)


async def search_and_fetch(
    query: str,
    max_results: int = None,
    event_callback: FetchEventCallback | None = None,
    *,
    days: int | None = None,
    include_domains: list[str] | None = None,
) -> list[SearchResult]:
    """Search and immediately fetch full text for all results."""
    results = await search_web(
        query,
        max_results,
        days=days,
        include_domains=include_domains,
    )

    async def fetch_one(result: SearchResult) -> SearchResult:
        result.full_text = await fetch_page(result.url, event_callback=event_callback)
        return result

    return await asyncio.gather(*[fetch_one(r) for r in results])


async def search_topic_with_seeds(
    query: str,
    max_results: int = None,
    event_callback: FetchEventCallback | None = None,
) -> tuple[list[SearchResult], list[str]]:
    """Broad search plus DACH registry site: seeds when intent matches."""
    if max_results is None:
        max_results = config.search_max_results

    topics_searched = [query]
    recency_days = config.research_recency_days if has_dach_intent(query) else None

    if not config.dach_seeds_enabled or not has_dach_intent(query):
        results = await search_and_fetch(
            query,
            max_results,
            event_callback=event_callback,
            days=recency_days,
        )
        return results, topics_searched

    seed_queries = build_seed_queries(query, max_seeds=config.dach_max_seed_queries)
    broad_budget = max(max_results - len(seed_queries) * config.dach_seed_results_per_query, 3)

    if event_callback and seed_queries:
        await event_callback("dach_seeds_start", {
            "seed_count": len(seed_queries),
            "seeds": seed_queries,
            "recency_days": recency_days,
        })

    broad_results = await search_and_fetch(
        query,
        broad_budget,
        event_callback=event_callback,
        days=recency_days,
    )
    all_results = list(broad_results)

    for seed_query in seed_queries:
        topics_searched.append(seed_query)
        seed_hits = await search_and_fetch(
            seed_query,
            config.dach_seed_results_per_query,
            event_callback=event_callback,
            days=recency_days,
        )
        all_results.extend(seed_hits)

    unique = deduplicate_search_results(all_results)
    return unique[:max_results], topics_searched
