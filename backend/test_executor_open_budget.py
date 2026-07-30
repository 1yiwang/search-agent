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
        patch("sources.executor._site_searches", new_callable=AsyncMock, return_value=(site_hits, ["site:q"])),
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


async def _test_open_query_count_scales_with_budget():
    decision = RouterDecision(
        selected_source_ids=["pei"],
        site_queries=[],
        defer_open_web=False,
    )
    seen: set[str] = set()
    open_queries = [
        "q1 European defaults",
        "q2 European spreads",
        "q3 European ELTIF",
        "q4 European volume",
    ]

    with (
        patch("sources.executor._site_searches", new_callable=AsyncMock, return_value=([], [])),
        patch(
            "sources.executor.search_and_fetch",
            new_callable=AsyncMock,
            return_value=[
                SearchResult(url="https://x.com/1", title="X", snippet="s", full_text="ok"),
            ],
        ) as mock_open,
        patch("sources.executor.config.min_unique_domains_target", 3),
    ):
        await execute_router_decision(
            "European private debt",
            decision,
            seen,
            budget_remaining=9,
            force_open_web=True,
            open_queries=open_queries,
        )

    # open_budget ≈ max(2, 9//3)=3 reserved; with force open and empty site, open_budget=9
    # open_cap=6; max_open = min(4 queries, min(6, max(2, 9//2)=4)) = 4
    assert mock_open.await_count == 4
    print("test_open_query_count_scales_with_budget: PASS")


async def _test_open_query_cap_six_on_force_open():
    decision = RouterDecision(
        selected_source_ids=[],
        site_queries=[],
        defer_open_web=False,
    )
    seen: set[str] = set()
    open_queries = [f"q{i} European AI video" for i in range(1, 8)]

    with (
        patch("sources.executor._site_searches", new_callable=AsyncMock, return_value=([], [])),
        patch(
            "sources.executor.search_and_fetch",
            new_callable=AsyncMock,
            return_value=[
                SearchResult(url="https://x.com/1", title="X", snippet="s", full_text="ok"),
            ],
        ) as mock_open,
        patch("sources.executor.config.min_unique_domains_target", 3),
        patch("sources.executor.config.open_max_queries_per_hop", 6),
        patch("sources.executor.config.tavily_deep_on_open_web", True),
    ):
        await execute_router_decision(
            "European AI short video",
            decision,
            seen,
            budget_remaining=18,
            force_open_web=True,
            open_queries=open_queries,
        )

    # open_budget=18; max_open = min(7, min(6, max(2, 18//2)=9)) = 6
    assert mock_open.await_count == 6
    print("test_open_query_cap_six_on_force_open: PASS")


async def _test_site_search_failover_on_empty():
    decision = RouterDecision(
        site_queries=["site:stepstonegroup.com European private debt"],
        defer_open_web=True,
    )
    seen: set[str] = set()
    events: list[tuple[str, dict]] = []

    async def emit(event_type: str, data: dict):
        events.append((event_type, data))

    failover_hit = [
        SearchResult(
            url="https://www.privateequityinternational.com/a",
            title="PEI",
            snippet="s",
            full_text="ok",
        ),
    ]

    async def fake_search(query, max_results, event_callback=None, days=None):
        if "privateequityinternational.com" in query or "pei.com" in query:
            return failover_hit
        if "preqin" in query:
            return failover_hit
        return []

    with (
        patch("sources.executor.search_and_fetch", side_effect=fake_search),
        patch("sources.executor.config.min_unique_domains_target", 3),
        patch(
            "sources.executor.alternate_site_queries",
            return_value=["site:privateequityinternational.com European private debt"],
        ),
    ):
        results, searched = await execute_router_decision(
            "European private debt",
            decision,
            seen,
            budget_remaining=9,
            event_callback=emit,
            missing_dimensions=["fundraising"],
            force_open_web=False,
            open_queries=[],
        )

    assert any(e[0] == "site_search_failover" for e in events)
    assert any("privateequityinternational.com" in q for q in searched)
    assert results and "privateequityinternational.com" in results[0].url
    print("test_site_search_failover_on_empty: PASS")


async def _test_fetch_failover_cross_source():
    decision = RouterDecision(
        direct_url_fetches=["https://www.stepstonegroup.com/news-insights/broken/"],
        defer_open_web=True,
    )
    seen: set[str] = set()
    events: list[tuple[str, dict]] = []

    async def emit(event_type: str, data: dict):
        events.append((event_type, data))

    async def fake_fetch(url: str, event_callback=None):
        if "stepstonegroup.com" in url:
            return "[Failed to fetch]"
        return "full article text about direct lending"

    with (
        patch("sources.executor.alternate_entry_urls", return_value=[]),
        patch(
            "sources.executor.alternate_source_entry_urls",
            return_value=["https://www.privateequityinternational.com/insights/ok/"],
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
            missing_dimensions=["fundraising"],
        )

    assert any(e[0] == "fetch_failover" for e in events)
    assert results and "privateequityinternational.com" in results[0].url
    print("test_fetch_failover_cross_source: PASS")


if __name__ == "__main__":
    asyncio.run(_test_open_budget_reserved_when_defer())
    asyncio.run(_test_fetch_retry_alternate_url())
    asyncio.run(_test_open_query_count_scales_with_budget())
    asyncio.run(_test_open_query_cap_six_on_force_open())
    asyncio.run(_test_site_search_failover_on_empty())
    asyncio.run(_test_fetch_failover_cross_source())
    print("All executor tests passed!")
