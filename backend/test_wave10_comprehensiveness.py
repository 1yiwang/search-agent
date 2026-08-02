"""Wave 10: parallel open search + rank-then-fetch + general synthesis gates."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from models import ExtractedFact, SearchResult


def test_rank_prefers_topic_overlap_and_authority():
    from rank_fetch import rank_search_results

    topic = "China Unicom Switzerland telecom market"
    weak = SearchResult(
        url="https://blog.example.cn/random",
        title="Random blog",
        snippet="unrelated text",
    )
    strong = SearchResult(
        url="https://www.bakom.admin.ch/report",
        title="Swiss telecom market report",
        snippet="China Unicom Switzerland market share telecom",
    )
    ranked = rank_search_results(topic, [weak, strong])
    assert ranked[0].url == strong.url
    print("test_rank_prefers_topic_overlap_and_authority: PASS")


def test_select_top_k_limits_fetch_candidates():
    from rank_fetch import select_top_k_for_fetch

    topic = "Switzerland telecom"
    results = [
        SearchResult(url=f"https://a{i}.com/{i}", title=f"T{i}", snippet="Switzerland telecom market")
        for i in range(10)
    ]
    top = select_top_k_for_fetch(topic, results, k=3)
    assert len(top) == 3
    print("test_select_top_k_limits_fetch_candidates: PASS")


async def _test_open_queries_run_in_parallel():
    from sources.executor import execute_router_decision
    from sources.models import RouterDecision

    decision = RouterDecision(site_queries=[], defer_open_web=False)
    seen: set[str] = set()
    open_queries = ["q1 Switzerland", "q2 Schweiz", "q3 Suisse"]
    call_order: list[str] = []
    inflight = {"n": 0, "max": 0}

    async def fake_search(query, max_results, **kwargs):
        inflight["n"] += 1
        inflight["max"] = max(inflight["max"], inflight["n"])
        call_order.append(query)
        await asyncio.sleep(0.05)
        inflight["n"] -= 1
        return [
            SearchResult(
                url=f"https://example.com/{query[:2]}",
                title=query,
                snippet=query,
                full_text="",
            )
        ]

    async def fake_fetch(url, event_callback=None):
        return f"body for {url}"

    with (
        patch("sources.executor.search_web", side_effect=fake_search),
        patch("sources.executor.fetch_page", side_effect=fake_fetch),
        patch("sources.executor.config.open_max_queries_per_hop", 6),
        patch("sources.executor.config.tavily_deep_on_open_web", False),
        patch("sources.executor.config.fetch_top_k_per_hop", 10),
        patch("sources.executor.config.open_search_parallel", True),
    ):
        results, searched, _leftover = await execute_router_decision(
            "Switzerland telecom",
            decision,
            seen,
            budget_remaining=12,
            force_open_web=True,
            open_queries=open_queries,
        )

    assert len(searched) >= 3
    assert inflight["max"] >= 2, "expected concurrent open searches"
    assert results
    print("test_open_queries_run_in_parallel: PASS")


def test_general_coverage_requires_synthesis_gates():
    from coverage import evaluate_coverage

    def _fact(text: str, url: str) -> ExtractedFact:
        return ExtractedFact(
            fact=text,
            source_url=url,
            source_title="t",
            quoted_text=text,
            confidence="medium",
        )

    topic = "European AI platforms overview"
    # 8 facts, 5 domains, but no examples/challenges/experts language
    facts = [
        _fact(f"Platform {i} has users in Europe and growing revenue.", f"https://d{i}.com/{i}")
        for i in range(8)
    ]
    result = evaluate_coverage(
        topic, facts, hop=0, max_hops=5, coverage_threshold=0.65,
        sources_budget_remaining=10, stagnant_hops=0, min_unique_domains=5,
    )
    assert result.should_continue is True
    assert any(d in result.missing_dimensions for d in ("examples", "challenges", "experts"))
    print("test_general_coverage_requires_synthesis_gates: PASS")


def test_general_coverage_stops_when_gates_met():
    from coverage import evaluate_coverage

    def _fact(text: str, url: str) -> ExtractedFact:
        return ExtractedFact(
            fact=text,
            source_url=url,
            source_title="t",
            quoted_text=text,
            confidence="medium",
        )

    topic = "European AI platforms overview"
    facts = [
        _fact("Case study: Platform A deployed in hospitals.", "https://a.com/1"),
        _fact("Expert analysts say adoption is rising.", "https://b.com/2"),
        _fact("Challenges include regulation and data privacy limits.", "https://c.com/3"),
        _fact("Market share grew in Germany.", "https://d.com/4"),
        _fact("Revenue exceeded forecasts in France.", "https://e.com/5"),
        _fact("Users increased across the EU.", "https://f.com/6"),
        _fact("Competition intensified among vendors.", "https://g.com/7"),
        _fact("Funding rounds continued in 2026.", "https://h.com/8"),
    ]
    result = evaluate_coverage(
        topic, facts, hop=0, max_hops=5, coverage_threshold=0.65,
        sources_budget_remaining=10, stagnant_hops=0, min_unique_domains=5,
    )
    assert not result.should_continue
    print("test_general_coverage_stops_when_gates_met: PASS")


if __name__ == "__main__":
    test_rank_prefers_topic_overlap_and_authority()
    test_select_top_k_limits_fetch_candidates()
    asyncio.run(_test_open_queries_run_in_parallel())
    test_general_coverage_requires_synthesis_gates()
    test_general_coverage_stops_when_gates_met()
    print("All Wave 10 tests passed!")
