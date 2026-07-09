"""Chained fetch: Jina (when configured) → httpx → Tavily extract."""
from collections.abc import Awaitable, Callable
from typing import Any

from config import config
from .fetch_httpx import HttpxFetchProvider
from .fetch_jina import JinaFetchProvider
from .fetch_tavily_extract import TavilyExtractFetchProvider
from .fetch_utils import is_fetch_failure

FetchEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

_BASE_CHAIN = (
    ("httpx", HttpxFetchProvider),
    ("jina", JinaFetchProvider),
    ("tavily_extract", TavilyExtractFetchProvider),
)


def _active_chain() -> tuple[tuple[str, type], ...]:
    """Prefer Jina reader first when API key is set (cleaner citation snapshots)."""
    if config.jina_api_key:
        return (
            ("jina", JinaFetchProvider),
            ("httpx", HttpxFetchProvider),
            ("tavily_extract", TavilyExtractFetchProvider),
        )
    return _BASE_CHAIN


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
        chain = _active_chain()

        for index, (provider_name, provider_cls) in enumerate(chain):
            provider = provider_cls()
            last_text = await provider.fetch(url, timeout=timeout)
            if not is_fetch_failure(last_text):
                return last_text, fallbacks

            reason = last_text.removeprefix(f"[Failed to fetch {url}: ").rstrip("]")
            if index + 1 < len(chain):
                next_name = chain[index + 1][0]
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
