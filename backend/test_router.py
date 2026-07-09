"""Tests for Source Router constraints."""
from unittest.mock import AsyncMock, MagicMock, patch

from sources.catalog import clear_catalog_cache, filter_candidates
from sources.models import SourceEntry
from sources.router import _enforce_constraints, fallback_decision, route_sources


def test_enforce_constraints_rejects_unknown_ids():
    candidates = [
        SourceEntry(id="a", name="A", domain="a.com", search_templates=["site:a.com {topic}"]),
        SourceEntry(id="b", name="B", domain="b.com"),
    ]
    raw = {
        "selected_source_ids": ["a", "evil"],
        "site_queries": ["site:a.com test"],
        "direct_url_fetches": ["https://evil.com/page"],
        "rationale": "test",
    }
    decision = _enforce_constraints(raw, candidates, "European private debt")
    assert decision.selected_source_ids == ["a"]
    assert "https://evil.com/page" not in decision.direct_url_fetches
    print("test_enforce_constraints_rejects_unknown_ids: PASS")


def test_fallback_decision_uses_seeds():
    clear_catalog_cache()
    topic = "European private debt direct lending 2026"
    candidates = filter_candidates(topic, max_candidates=5)
    decision = fallback_decision(topic, candidates)
    assert decision.fallback is True
    assert decision.selected_source_ids
    assert decision.site_queries or decision.direct_url_fetches
    print("test_fallback_decision_uses_seeds: PASS")


async def _test_route_sources_fallback_without_llm():
    clear_catalog_cache()
    topic = "European corporate direct lending fundraising 2026"
    candidates = filter_candidates(topic, max_candidates=5)
    with patch("sources.router.get_request_keys", return_value=None):
        decision = await route_sources(topic, candidates=candidates)
    assert decision.fallback is True
    assert decision.selected_source_ids
    print("test_route_sources_fallback_without_llm: PASS")


async def _test_route_sources_mock_llm():
    clear_catalog_cache()
    topic = "European corporate direct lending fundraising 2026"
    candidates = filter_candidates(topic, max_candidates=8)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='''{
        "selected_source_ids": ["stepstone_insights", "pei"],
        "direct_url_fetches": [],
        "site_queries": ["site:stepstonegroup.com European direct lending"],
        "rationale": "Manager research first",
        "defer_open_web": true
    }'''))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_keys = MagicMock(llm_api_key="sk-test", llm_model="test")

    with (
        patch("sources.router.get_request_keys", return_value=mock_keys),
        patch("sources.router.get_openai_client", return_value=mock_client),
        patch("sources.router.config.router_enabled", True),
    ):
        decision = await route_sources(topic, candidates=candidates)

    assert "stepstone_insights" in decision.selected_source_ids
    assert decision.rationale
    print("test_route_sources_mock_llm: PASS")


if __name__ == "__main__":
    import asyncio

    test_enforce_constraints_rejects_unknown_ids()
    test_fallback_decision_uses_seeds()
    asyncio.run(_test_route_sources_fallback_without_llm())
    asyncio.run(_test_route_sources_mock_llm())
    print("All router tests passed!")
