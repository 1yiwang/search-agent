"""DuckDuckGo search provider."""
import asyncio

from duckduckgo_search import DDGS

from models import SearchResult


class DDGSearchProvider:
    name = "ddg"

    async def search(self, query: str, max_results: int, **kwargs) -> list[SearchResult]:
        """Search via DuckDuckGo with rate-limit backoff."""
        loop = asyncio.get_event_loop()
        last_error = None

        for attempt in range(3):
            try:
                raw_results = await loop.run_in_executor(
                    None,
                    lambda: list(DDGS().text(query, max_results=max_results)),
                )
                return [
                    SearchResult(
                        url=r.get("href", ""),
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                    )
                    for r in raw_results
                ]
            except Exception as e:
                last_error = e
                wait = (attempt + 1) * 3
                print(
                    f"[search:ddg] attempt {attempt + 1}/3 failed ({e}), "
                    f"retrying in {wait}s..."
                )
                await asyncio.sleep(wait)

        print(f"[search:ddg] all retries exhausted: {last_error}")
        return []
