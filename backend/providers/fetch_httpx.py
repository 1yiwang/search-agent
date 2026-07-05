"""Direct HTTP fetch + HTML-to-markdown provider."""
import httpx
from markdownify import markdownify as md

from config import config

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}


class HttpxFetchProvider:
    name = "httpx"

    async def fetch(self, url: str, timeout: int = 15) -> str:
        """Fetch a page and convert HTML to markdown text."""
        max_chars = config.fetch_max_chars
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=_DEFAULT_HEADERS)
                response.raise_for_status()
                text = md(
                    response.text,
                    heading_style="ATX",
                    strip=["script", "style", "nav", "footer"],
                )
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n\n[... content truncated ...]"
                return text.strip()
            except Exception as e:
                return f"[Failed to fetch {url}: {e}]"
