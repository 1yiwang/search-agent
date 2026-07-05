"""Tests for provider registry and Tavily search."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from config import config
from models import SearchResult
from providers import (
    available_search_providers,
    get_search_provider,
    reset_providers,
)
from providers.search_tavily import TavilySearchProvider


def test_available_search_providers():
    assert set(available_search_providers()) == {"ddg", "tavily"}


def test_get_provider_by_name():
    reset_providers()
    original = config.search_provider
    try:
        config.search_provider = "tavily"
        assert get_search_provider().name == "tavily"
        reset_providers()
        config.search_provider = "ddg"
        assert get_search_provider().name == "ddg"
    finally:
        config.search_provider = original
        reset_providers()


async def _test_tavily_fallback_without_api_key():
    provider = TavilySearchProvider()
    original_key = config.tavily_api_key
    config.tavily_api_key = ""
    try:
        with patch(
            "providers.search_tavily.DDGSearchProvider"
        ) as mock_ddg_cls:
            mock_ddg = mock_ddg_cls.return_value
            mock_ddg.search = AsyncMock(
                return_value=[
                    SearchResult(url="https://a.com", title="A", snippet="x")
                ]
            )
            results = await provider.search("test query", 3)
            mock_ddg.search.assert_awaited_once_with("test query", 3)
            assert len(results) == 1
    finally:
        config.tavily_api_key = original_key


async def _test_tavily_parses_api_response():
    provider = TavilySearchProvider()
    original_key = config.tavily_api_key
    config.tavily_api_key = "tvly-test"
    try:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Example",
                    "content": "snippet text",
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("providers.search_tavily.httpx.AsyncClient", return_value=mock_client):
            results = await provider.search("example", 5)

        assert len(results) == 1
        assert results[0].url == "https://example.com"
        assert results[0].title == "Example"
        assert results[0].snippet == "snippet text"
    finally:
        config.tavily_api_key = original_key


def test_fetch_registry():
    from providers import available_fetch_providers, get_fetch_provider

    reset_providers()
    assert "httpx" in available_fetch_providers()
    assert get_fetch_provider().name == "httpx"


if __name__ == "__main__":
    test_available_search_providers()
    test_get_provider_by_name()
    asyncio.run(_test_tavily_fallback_without_api_key())
    asyncio.run(_test_tavily_parses_api_response())
    test_fetch_registry()
    print("test_providers: PASS")
