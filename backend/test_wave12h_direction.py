"""Wave 12h: CJK-aware tokens + leftover open queries."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from models import BriefDimension, ResearchBrief, SearchResult
from text_tokens import keyword_list, tokens


def test_tokens_chinese_ngrams():
    toks = tokens("梳理瑞士电信Swisscom份额与监管")
    assert any("瑞士" in t or "电信" in t for t in toks)
    assert "swisscom" in [t.lower() for t in toks]
    print("test_tokens_chinese_ngrams: PASS")


def test_brief_coverage_dims_uses_cjk_tokens():
    from research_loop import _brief_coverage_dims

    brief = ResearchBrief(
        topic="中国联通进入瑞士电信市场",
        problem_restatement="x",
        framework_id="market_entry",
        dimensions=[
            BriefDimension(
                title="竞争格局",
                research_goal="梳理Swisscom Sunrise Salt份额与ARPU",
                direction_detail="调研Swisscom、Sunrise、Salt的份额与定价",
                queries=["Swisscom market share"],
                phase_id="industry_structure",
                direction_id="industry_structure",
                entities=["Swisscom", "Sunrise"],
            ),
        ],
    )
    dims = _brief_coverage_dims(brief)
    assert dims
    _dim_id, _goal, keywords = dims[0]
    joined = " ".join(keywords).lower()
    assert "swisscom" in joined or "份额" in joined or "竞争" in joined
    # Must not be a single giant unsplit Chinese string as sole keyword
    assert not (len(keywords) == 1 and len(keywords[0]) > 20 and " " not in keywords[0])
    print("test_brief_coverage_dims_uses_cjk_tokens: PASS")


def test_keyword_list_merges():
    ks = keyword_list("Swisscom份额", "Sunrise Salt", max_tokens=12)
    assert len(ks) >= 2
    print("test_keyword_list_merges: PASS")


async def _test_leftover_open_queries_returned():
    from sources.executor import execute_router_decision
    from sources.models import RouterDecision

    decision = RouterDecision(
        site_queries=[],
        defer_open_web=False,
        rationale="test",
    )
    open_queries = [f"q{i} swiss telecom" for i in range(8)]

    async def fake_search(query, max_results, days=None):
        return [
            SearchResult(
                url=f"https://example.com/{query[:8]}",
                title=query,
                snippet="s",
                full_text="body " * 20,
            )
        ]

    with (
        patch("sources.executor.search_web", side_effect=fake_search),
        patch("sources.executor.fetch_page", new_callable=AsyncMock, return_value="full"),
        patch("sources.executor.config.open_max_queries_per_hop", 3),
        patch("sources.executor.config.fetch_top_k_per_hop", 6),
        patch("sources.executor.config.open_search_parallel", False),
        patch("sources.executor.config.min_unique_domains_target", 99),
    ):
        results, searched, leftover = await execute_router_decision(
            "Swiss telecom",
            decision,
            set(),
            budget_remaining=10,
            force_open_web=True,
            open_queries=open_queries,
        )

    assert len(searched) <= 3
    assert leftover
    assert all(q in open_queries for q in leftover)
    assert not set(leftover) & set(searched)
    assert results
    print("test_leftover_open_queries_returned: PASS")


def test_parse_brief_fills_direction_contract():
    from brief import _parse_brief_payload

    brief = _parse_brief_payload(
        {
            "problem_restatement": "中国联通瑞士电信机会",
            "framework_id": "market_entry",
            "dimensions": [
                {
                    "title": "竞争格局",
                    "research_goal": "梳理 Swisscom Sunrise Salt 份额",
                    "direction_detail": "调研Swisscom、Sunrise、Salt的市场份额与ARPU，对照BAKOM数据",
                    "phase_id": "industry_structure",
                    "queries": ["Swisscom market share Switzerland"],
                    "priority": 1,
                },
            ],
            "deprioritize": [],
        },
        topic="中国联通进入瑞士电信市场机会",
        framework_id="market_entry",
        answers={},
    )
    d0 = brief.dimensions[0]
    assert d0.direction_id == "industry_structure" or d0.phase_id == "industry_structure"
    assert d0.entities, "entities should be harvested"
    print("test_parse_brief_fills_direction_contract: PASS")


if __name__ == "__main__":
    test_tokens_chinese_ngrams()
    test_keyword_list_merges()
    test_brief_coverage_dims_uses_cjk_tokens()
    test_parse_brief_fills_direction_contract()
    asyncio.run(_test_leftover_open_queries_returned())
    print("ALL PASS")
