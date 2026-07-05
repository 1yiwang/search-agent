"""Web search and page fetching module (facade over providers)."""
import asyncio

from config import config
from models import SearchResult
from providers import get_fetch_provider, get_search_provider


async def search_web(query: str, max_results: int = None) -> list[SearchResult]:
    """Search the web using the configured search provider."""
    if max_results is None:
        max_results = config.search_max_results
    provider = get_search_provider()
    return await provider.search(query, max_results)


async def fetch_page(url: str, timeout: int = 15) -> str:
    """Fetch a webpage using the configured fetch provider."""
    provider = get_fetch_provider()
    return await provider.fetch(url, timeout)


async def search_and_fetch(query: str, max_results: int = None) -> list[SearchResult]:
    """Search and immediately fetch full text for all results."""
    results = await search_web(query, max_results)

    async def fetch_one(result: SearchResult) -> SearchResult:
        result.full_text = await fetch_page(result.url)
        return result

    return await asyncio.gather(*[fetch_one(r) for r in results])
