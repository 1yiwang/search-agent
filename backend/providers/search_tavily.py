"""Tavily search provider with DuckDuckGo fallback."""
import httpx

from config import config
from llm_context import get_tavily_api_key
from models import SearchResult

from .search_ddg import DDGSearchProvider

_TAVILY_URL = "https://api.tavily.com/search"


class TavilySearchProvider:
    name = "tavily"

    async def search(
        self,
        query: str,
        max_results: int,
        *,
        days: int | None = None,
        include_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search via Tavily API; fall back to DDG on missing key or failure."""
        key = get_tavily_api_key() or config.tavily_api_key
        if not key:
            print("[search:tavily] TAVILY_API_KEY not set, falling back to ddg")
            return await DDGSearchProvider().search(query, max_results)

        try:
            results = await self._tavily_search(
                query,
                max_results,
                days=days,
                include_domains=include_domains,
            )
            if results:
                return results
            print("[search:tavily] empty results, falling back to ddg")
        except Exception as e:
            print(f"[search:tavily] failed ({e}), falling back to ddg")

        return await DDGSearchProvider().search(query, max_results)

    async def _tavily_search(
        self,
        query: str,
        max_results: int,
        *,
        days: int | None = None,
        include_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        api_key = get_tavily_api_key() or config.tavily_api_key
        payload: dict = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": config.tavily_search_depth,
        }
        if days is not None and days > 0:
            payload["days"] = days
        if include_domains:
            payload["include_domains"] = include_domains
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
