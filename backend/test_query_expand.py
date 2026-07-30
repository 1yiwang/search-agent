"""Tests for deterministic query expansion (Step 43)."""
from datetime import date

from coverage import GapHint
from query_expand import (
    DIMENSION_INFO_TYPES,
    expand_queries,
    gap_hints_to_router_hints,
)
from sources.models import SourceEntry


def _candidate(source_id: str, domain: str) -> SourceEntry:
    return SourceEntry(
        id=source_id,
        name=source_id,
        domain=domain,
        tags=["credit"],
        search_templates=[f"site:{domain} {{topic}} private debt"],
        entry_urls=[f"https://www.{domain}/insights/"],
    )


def test_expand_generates_site_and_open_per_gap():
    candidates = [
        _candidate("pei", "privateequityinternational.com"),
        _candidate("stepstone_insights", "stepstonegroup.com"),
        _candidate("fnlondon", "fnlondon.com"),
    ]
    hints = [
        GapHint(dimension="fundraising", research_goal="EU vs US fundraising"),
        GapHint(dimension="credit_risk", research_goal="defaults and leverage"),
    ]
    result = expand_queries(
        "European direct lending trends 2026",
        hints,
        candidates,
        current_date=date(2026, 7, 9),
        max_queries=6,
    )
    assert len(result.queries) <= 6
    channels = [q.channel for q in result.queries]
    assert "site" in channels
    assert "open" in channels
    for q in result.queries:
        assert q.research_goal
        assert q.template_id in DIMENSION_INFO_TYPES["fundraising"] + DIMENSION_INFO_TYPES["credit_risk"] + list(
            {"facts_data", "examples", "experts", "trends", "comparisons", "challenges"}
        )
    print("test_expand_generates_site_and_open_per_gap: PASS")


def test_expand_injects_date_granularity():
    candidates = [_candidate("pei", "privateequityinternational.com")]
    hints = [GapHint(dimension="returns_spreads", research_goal="yields and spreads")]
    result = expand_queries(
        "European direct lending",
        hints,
        candidates,
        current_date=date(2026, 7, 9),
        max_queries=2,
    )
    joined = " ".join(q.query for q in result.queries)
    assert "2026-07" in joined or "July 2026" in joined or "H1 2026" in joined or "H2 2026" in joined
    print("test_expand_injects_date_granularity: PASS")


def test_expand_hard_cap():
    candidates = [
        _candidate("pei", "privateequityinternational.com"),
        _candidate("stepstone_insights", "stepstonegroup.com"),
        _candidate("fnlondon", "fnlondon.com"),
    ]
    hints = [
        GapHint(dimension="fundraising", research_goal="g1"),
        GapHint(dimension="volume_deals", research_goal="g2"),
        GapHint(dimension="credit_risk", research_goal="g3"),
    ]
    result = expand_queries(
        "European PD",
        hints,
        candidates,
        current_date=date(2026, 7, 9),
        max_queries=4,
    )
    assert len(result.queries) == 4
    assert result.capped is True
    print("test_expand_hard_cap: PASS")


def test_gap_hints_to_router_hints():
    hints = [
        GapHint(dimension="fundraising", research_goal="goal A", suggested_queries=["q1", "q2"]),
        GapHint(dimension="credit_risk", research_goal="goal B"),
    ]
    out = gap_hints_to_router_hints(hints)
    assert out[0].startswith("goal A")
    assert "dimension=fundraising" in out[0]
    assert "try: q1; q2" in out[0]
    assert out[1] == "goal B | dimension=credit_risk"
    print("test_gap_hints_to_router_hints: PASS")


def test_preferred_source_ids_for_gaps():
    from query_expand import preferred_source_ids_for_gaps

    hints = [
        GapHint(dimension="fundraising", research_goal="g"),
        GapHint(dimension="credit_risk", research_goal="g"),
    ]
    ids = preferred_source_ids_for_gaps(hints)
    assert "pei" in ids
    assert ids.index("pei") == 0
    assert "altassets" in ids
    print("test_preferred_source_ids_for_gaps: PASS")


def test_alternate_site_queries_switches_domain():
    from query_expand import alternate_site_queries

    alts = alternate_site_queries(
        "site:stepstonegroup.com European private debt",
        "European private debt",
        missing_dimensions=["fundraising"],
        max_alternates=2,
    )
    assert alts
    assert all("stepstonegroup.com" not in q for q in alts)
    assert any("site:" in q for q in alts)
    print("test_alternate_site_queries_switches_domain: PASS")


def test_open_query_embeds_research_goal():
    candidates = [_candidate("pei", "privateequityinternational.com")]
    hints = [
        GapHint(
            dimension="credit_risk",
            research_goal="private debt defaults leverage credit risk",
        ),
    ]
    result = expand_queries(
        "European corporate direct lending fundraising trends H1 2026",
        hints,
        candidates,
        current_date=date(2026, 7, 9),
        max_queries=4,
    )
    open_qs = [q for q in result.queries if q.channel == "open"]
    assert open_qs
    joined = " ".join(q.query.lower() for q in open_qs)
    assert "default" in joined or "leverage" in joined or "credit" in joined
    print("test_open_query_embeds_research_goal: PASS")


def test_info_type_rotates_across_hops():
    candidates = [_candidate("pei", "privateequityinternational.com")]
    hints = [GapHint(dimension="fundraising", research_goal="EU fundraising trends")]
    hop0 = expand_queries(
        "European PD", hints, candidates, current_date=date(2026, 7, 9), hop=0,
    )
    hop1 = expand_queries(
        "European PD", hints, candidates, current_date=date(2026, 7, 9), hop=1,
    )
    open0 = next(q for q in hop0.queries if q.channel == "open")
    open1 = next(q for q in hop1.queries if q.channel == "open")
    # fundraising info_types = [trends, facts_data]; hop0 open uses facts_data, hop1 uses trends
    assert open0.template_id != open1.template_id
    print("test_info_type_rotates_across_hops: PASS")


def test_general_expand_is_open_only():
    hints = [
        GapHint(dimension="_empty", research_goal="Primary sources for the topic"),
        GapHint(dimension="ranking", research_goal="Rankings market share"),
    ]
    result = expand_queries(
        "European AI short video platform ranking H1 2026",
        hints,
        candidates=[],
        current_date=date(2026, 7, 9),
        max_queries=6,
    )
    assert result.queries
    assert all(q.channel == "open" for q in result.queries)
    joined = " ".join(q.query.lower() for q in result.queries)
    assert "ranking" in joined or "landscape" in joined or "market" in joined
    print("test_general_expand_is_open_only: PASS")


if __name__ == "__main__":
    test_expand_generates_site_and_open_per_gap()
    test_expand_injects_date_granularity()
    test_expand_hard_cap()
    test_gap_hints_to_router_hints()
    test_preferred_source_ids_for_gaps()
    test_alternate_site_queries_switches_domain()
    test_open_query_embeds_research_goal()
    test_info_type_rotates_across_hops()
    test_general_expand_is_open_only()
    print("All query expand tests passed!")
