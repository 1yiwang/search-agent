"""Tests for provider registry."""
from providers import (
    available_fetch_providers,
    available_search_providers,
    get_fetch_provider,
    get_search_provider,
    reset_providers,
)


def test_search_registry():
    reset_providers()
    assert "ddg" in available_search_providers()
    provider = get_search_provider()
    assert provider.name == "ddg"


def test_fetch_registry():
    reset_providers()
    assert "httpx" in available_fetch_providers()
    provider = get_fetch_provider()
    assert provider.name == "httpx"


if __name__ == "__main__":
    test_search_registry()
    test_fetch_registry()
    print("test_providers: PASS")
