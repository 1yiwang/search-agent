"""Jina Reader fetch provider."""
import httpx

from config import config

from .fetch_utils import is_fetch_failure, truncate


class JinaFetchProvider:
    name = "jina"

    async def fetch(self, url: str, timeout: int = 15) -> str:
        headers = {"Accept": "text/markdown"}
        if config.jina_api_key:
            headers["Authorization"] = f"Bearer {config.jina_api_key}"

        reader_url = f"https://r.jina.ai/{url}"
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(reader_url, headers=headers)
                response.raise_for_status()
                text = response.text.strip()
                if is_fetch_failure(text):
                    return f"[Failed to fetch {url}: empty Jina response]"
                return truncate(text)
        except Exception as e:
            return f"[Failed to fetch {url}: {e}]"
