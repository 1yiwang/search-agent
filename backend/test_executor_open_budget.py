"""Tests for executor open-budget protection (Step 44)."""
import asyncio
from unittest.mock import AsyncMock, patch

from models import SearchResult
from sources.executor import execute_router_decision
from sources.models import RouterDecision


async def _test_open_budget_reserved_when_defer():
    decision = RouterDecision(
        selected_source_ids=["pei"],
        site_queries=["site:privateequityinternational.com private debt"],
        defer_open_web=True,
    )
    seen: set[str] = set()
    events: list[tuple[str, dict]] = []

    async def emit(event_type: str, data: dict):
        events.append((event_type, data))

    site_hits = [
        SearchResult(url="https://a.com/1", title="A", snippet="s", full_text="ok"),
        SearchResult(url="https://a.com/2", title="A2", snippet="s", full_text="ok"),
    ]
    open_hits = [
        SearchResult(url="https://b.com/1", title="B", snippet="s", full_text="ok"),
        SearchResult(url="https://c.com/1", title="C", snippet="s", full_text="ok"),
    ]

    with (
        patch("sources.executor._site_searches", new_callable=AsyncMock, return_value=site_hits),
        patch("sources.executor.search_and_fetch", new_callable=AsyncMock, return_value=open_hits) as mock_open,
        patch("sources.executor.config.min_unique_domains_target", 3),
    ):
        results, searched = await execute_router_decision(
            "European private debt",
            decision,
            seen,
            budget_remaining=9,
            event_callback=emit,
            missing_dimensions=["credit_risk"],
            open_queries=["European private debt defaults 2026-07"],
            gap_hop=True,
        )

    assert mock_open.await_count >= 1
    assert any(e[0] == "open_search_forced" for e in events)
    domains = {r.url.split("/")[2] for r in results}
    assert len(domains) >= 2
    assert any("defaults" in q or "private debt" in q for q in searched)
    print("test_open_budget_reserved_when_defer: PASS")


async def _test_fetch_retry_alternate_url():
    decision = RouterDecision(
        direct_url_fetches=["https://www.stepstonegroup.com/news-insights/broken/"],
        defer_open_web=True,
    )
    seen: set[str] = set()
    events: list[tuple[str, dict]] = []

    async def emit(event_type: str, data: dict):
        events.append((event_type, data))

    async def fake_fetch(url: str, event_callback=None):
        if "broken" in url:
            return "[Failed to fetch]"
        return "full article text about direct lending"

    with (
        patch(
            "sources.executor.alternate_entry_urls",
            return_value=["https://www.stepstonegroup.com/news-insights/ok/"],
        ),
        patch("sources.executor.fetch_page", side_effect=fake_fetch),
        patch("sources.executor.search_and_fetch", new_callable=AsyncMock, return_value=[]),
    ):
        results, _ = await execute_router_decision(
            "European private debt",
            decision,
            seen,
            budget_remaining=5,
            event_callback=emit,
            missing_dimensions=[],
        )

    assert any(e[0] == "fetch_retry" for e in events)
    assert results and "ok" in results[0].url
    print("test_fetch_retry_alternate_url: PASS")


if __name__ == "__main__":
    asyncio.run(_test_open_budget_reserved_when_defer())
    asyncio.run(_test_fetch_retry_alternate_url())
    print("All executor tests passed!")
