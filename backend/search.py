"""Web search and page fetching module (facade over providers)."""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from config import config
from models import SearchResult
from providers import get_fetch_provider, get_search_provider
from providers.fetch_chain import ChainedFetchProvider

FetchEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


async def search_web(query: str, max_results: int = None) -> list[SearchResult]:
    """Search the web using the configured search provider."""
    if max_results is None:
        max_results = config.search_max_results
    provider = get_search_provider()
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
) -> list[SearchResult]:
    """Search and immediately fetch full text for all results."""
    results = await search_web(query, max_results)

    async def fetch_one(result: SearchResult) -> SearchResult:
        result.full_text = await fetch_page(result.url, event_callback=event_callback)
        return result

    return await asyncio.gather(*[fetch_one(r) for r in results])
