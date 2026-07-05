"""Tavily extract API fetch provider."""
import httpx

from config import config

from .fetch_utils import is_fetch_failure, truncate

_TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


class TavilyExtractFetchProvider:
    name = "tavily_extract"

    async def fetch(self, url: str, timeout: int = 15) -> str:
        if not config.tavily_api_key:
            return f"[Failed to fetch {url}: TAVILY_API_KEY not set]"

        payload = {"api_key": config.tavily_api_key, "urls": [url]}
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(_TAVILY_EXTRACT_URL, json=payload)
                response.raise_for_status()
                data = response.json()

            failed = data.get("failed_results") or []
            if failed:
                reason = failed[0].get("error", "extract failed")
                return f"[Failed to fetch {url}: {reason}]"

            results = data.get("results") or []
            if not results:
                return f"[Failed to fetch {url}: no Tavily extract results]"

            item = results[0]
            title = item.get("title", "")
            body = item.get("raw_content", "") or ""
            text = f"# {title}\n\n{body}".strip() if title else body.strip()
            if is_fetch_failure(text):
                return f"[Failed to fetch {url}: empty Tavily extract]"
            return truncate(text)
        except Exception as e:
            return f"[Failed to fetch {url}: {e}]"
