"""Protocols for pluggable search and fetch backends."""
from typing import Protocol

from models import SearchResult


class SearchProvider(Protocol):
    """Web search backend (DuckDuckGo, Tavily, Brave, …)."""

    name: str

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Return normalized search hits."""
        ...


class FetchProvider(Protocol):
    """Page content backend (httpx, Jina, Tavily extract, …)."""

    name: str

    async def fetch(self, url: str, timeout: int = 15) -> str:
        """Return page body as markdown-ish text."""
        ...
