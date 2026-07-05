"""Tavily search provider with DuckDuckGo fallback."""
import httpx

from config import config
from models import SearchResult

from .search_ddg import DDGSearchProvider

_TAVILY_URL = "https://api.tavily.com/search"


class TavilySearchProvider:
    name = "tavily"

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Search via Tavily API; fall back to DDG on missing key or failure."""
        if not config.tavily_api_key:
            print("[search:tavily] TAVILY_API_KEY not set, falling back to ddg")
            return await DDGSearchProvider().search(query, max_results)

        try:
            results = await self._tavily_search(query, max_results)
            if results:
                return results
            print("[search:tavily] empty results, falling back to ddg")
        except Exception as e:
            print(f"[search:tavily] failed ({e}), falling back to ddg")

        return await DDGSearchProvider().search(query, max_results)

    async def _tavily_search(self, query: str, max_results: int) -> list[SearchResult]:
        payload = {
            "api_key": config.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": config.tavily_search_depth,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(_TAVILY_URL, json=payload)
            response.raise_for_status()
            data = response.json()

        return [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title", "") or item.get("url", ""),
                snippet=item.get("content", ""),
            )
            for item in data.get("results", [])
            if item.get("url")
        ]
