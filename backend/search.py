"""Web search and page fetching module."""
import asyncio
from duckduckgo_search import DDGS
import httpx
from markdownify import markdownify as md

from config import config
from models import SearchResult


async def search_web(query: str, max_results: int = None) -> list[SearchResult]:
    """Search the web using DuckDuckGo with rate-limit backoff."""
    if max_results is None:
        max_results = config.search_max_results

    loop = asyncio.get_event_loop()
    last_error = None

    for attempt in range(3):
        try:
            raw_results = await loop.run_in_executor(
                None,
                lambda: list(DDGS().text(query, max_results=max_results)),
            )
            results = []
            for r in raw_results:
                results.append(SearchResult(
                    url=r.get("href", ""),
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                ))
            return results
        except Exception as e:
            last_error = e
            wait = (attempt + 1) * 3  # 3s, 6s, 9s backoff
            print(f"[search] attempt {attempt + 1}/3 failed ({e}), retrying in {wait}s...")
            await asyncio.sleep(wait)

    print(f"[search] all retries exhausted: {last_error}")
    return []


async def fetch_page(url: str, timeout: int = 15) -> str:
    """Fetch a webpage and convert HTML to markdown text."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
            text = md(html, heading_style="ATX", strip=["script", "style", "nav", "footer"])
            # Truncate very long pages to ~8000 chars for LLM context
            if len(text) > 8000:
                text = text[:8000] + "\n\n[... content truncated ...]"
            return text.strip()
        except Exception as e:
            return f"[Failed to fetch {url}: {e}]"


async def search_and_fetch(query: str, max_results: int = None) -> list[SearchResult]:
    """Search and immediately fetch full text for all results."""
    results = await search_web(query, max_results)

    async def fetch_one(result: SearchResult) -> SearchResult:
        result.full_text = await fetch_page(result.url)
        return result

    return await asyncio.gather(*[fetch_one(r) for r in results])
