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


if __name__ == "__main__":
    test_expand_generates_site_and_open_per_gap()
    test_expand_injects_date_granularity()
    test_expand_hard_cap()
    test_gap_hints_to_router_hints()
    test_preferred_source_ids_for_gaps()
    print("All query expand tests passed!")
