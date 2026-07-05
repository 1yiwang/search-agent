"""Pluggable search and fetch providers (DeerFlow / GPT Researcher pattern)."""
from config import config

from .base import FetchProvider, SearchProvider
from .fetch_chain import ChainedFetchProvider
from .fetch_httpx import HttpxFetchProvider
from .fetch_jina import JinaFetchProvider
from .fetch_tavily_extract import TavilyExtractFetchProvider
from .search_ddg import DDGSearchProvider
from .search_tavily import TavilySearchProvider

_SEARCH_REGISTRY: dict[str, type] = {
    "ddg": DDGSearchProvider,
    "tavily": TavilySearchProvider,
}

_FETCH_REGISTRY: dict[str, type] = {
    "chain": ChainedFetchProvider,
    "httpx": HttpxFetchProvider,
    "jina": JinaFetchProvider,
    "tavily_extract": TavilyExtractFetchProvider,
}

_search_instance: SearchProvider | None = None
_fetch_instance: FetchProvider | None = None


def available_search_providers() -> list[str]:
    return sorted(_SEARCH_REGISTRY.keys())


def available_fetch_providers() -> list[str]:
    return sorted(_FETCH_REGISTRY.keys())


def get_search_provider() -> SearchProvider:
    """Return the configured search backend (singleton)."""
    global _search_instance
    name = config.search_provider.lower().strip()
    if name not in _SEARCH_REGISTRY:
        raise ValueError(
            f"Unknown SEARCH_PROVIDER={name!r}. "
            f"Choose from: {', '.join(available_search_providers())}"
        )
    if _search_instance is None or _search_instance.name != name:
        _search_instance = _SEARCH_REGISTRY[name]()
    return _search_instance


def get_fetch_provider() -> FetchProvider:
    """Return the configured fetch backend (singleton)."""
    global _fetch_instance
    name = config.fetch_provider.lower().strip()
    if name not in _FETCH_REGISTRY:
        raise ValueError(
            f"Unknown FETCH_PROVIDER={name!r}. "
            f"Choose from: {', '.join(available_fetch_providers())}"
        )
    if _fetch_instance is None or _fetch_instance.name != name:
        _fetch_instance = _FETCH_REGISTRY[name]()
    return _fetch_instance


def reset_providers() -> None:
    """Clear cached instances (for tests)."""
    global _search_instance, _fetch_instance
    _search_instance = None
    _fetch_instance = None
