"""Chained fetch: httpx → Jina → Tavily extract."""
from collections.abc import Awaitable, Callable
from typing import Any

from .fetch_httpx import HttpxFetchProvider
from .fetch_jina import JinaFetchProvider
from .fetch_tavily_extract import TavilyExtractFetchProvider
from .fetch_utils import is_fetch_failure

FetchEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

_CHAIN = (
    ("httpx", HttpxFetchProvider),
    ("jina", JinaFetchProvider),
    ("tavily_extract", TavilyExtractFetchProvider),
)


class ChainedFetchProvider:
    """Try fetch backends in order until one succeeds."""

    name = "chain"

    async def fetch(self, url: str, timeout: int = 15) -> str:
        text, _ = await self.fetch_with_meta(url, timeout=timeout)
        return text

    async def fetch_with_meta(
        self,
        url: str,
        timeout: int = 15,
        event_callback: FetchEventCallback | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        fallbacks: list[dict[str, str]] = []
        last_text = ""

        for index, (provider_name, provider_cls) in enumerate(_CHAIN):
            provider = provider_cls()
            last_text = await provider.fetch(url, timeout=timeout)
            if not is_fetch_failure(last_text):
                return last_text, fallbacks

            reason = last_text.removeprefix(f"[Failed to fetch {url}: ").rstrip("]")
            if index + 1 < len(_CHAIN):
                next_name = _CHAIN[index + 1][0]
                entry = {
                    "url": url,
                    "from": provider_name,
                    "to": next_name,
                    "reason": reason,
                }
                fallbacks.append(entry)
                if event_callback:
                    await event_callback("fetch_fallback", entry)
                print(
                    f"[fetch:chain] {provider_name} failed for {url[:60]}… "
                    f"→ trying {next_name}"
                )

        return last_text, fallbacks
