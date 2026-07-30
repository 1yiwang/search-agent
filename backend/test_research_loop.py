"""Tests for coverage-driven research loop (mocked I/O).

Step 50 locks the Wave 8 event chain:
  catalog → router → execute → coverage_eval → query_expand → hop-2 → report
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from models import ExtractedFact, ResearchRequest, SearchResult
from research_loop import run_research_loop
from sources.models import RouterDecision, SourceEntry


def _fact(text: str, url: str = "https://stepstonegroup.com/a") -> ExtractedFact:
    return ExtractedFact(
        fact=text,
        source_url=url,
        source_title="StepStone",
        quoted_text=text,
        confidence="high",
    )


def _candidate(source_id: str, domain: str) -> SourceEntry:
    return SourceEntry(
        id=source_id,
        name=source_id,
        domain=domain,
        tags=["credit"],
        search_templates=[f"site:{domain} {{topic}} private debt"],
        entry_urls=[f"https://www.{domain}/insights/"],
    )


async def _test_research_loop_completes_with_mocks():
    request = ResearchRequest(
        topic="European corporate direct lending fundraising trends 2026",
        max_sources=10,
    )
    decision = RouterDecision(
        selected_source_ids=["stepstone_insights"],
        site_queries=["site:stepstonegroup.com direct lending Europe"],
        rationale="test",
        defer_open_web=True,
    )
    rich_facts = [
        _fact("European fundraising rebounded in 2025.", "https://a.com/1"),
        _fact("Direct lending volumes within norms; refinancings share.", "https://b.com/2"),
        _fact("Gross yields 9-10%; spreads tightened.", "https://c.com/3"),
        _fact("Defaults below historical averages.", "https://d.com/4"),
        _fact("ELTIF evergreen product launch Europe.", "https://e.com/5"),
        _fact("Premium vs leveraged loans and high yield.", "https://f.com/6"),
    ]

    with (
        patch("research_loop.route_sources", new_callable=AsyncMock, return_value=decision),
        patch("research_loop.execute_router_decision", new_callable=AsyncMock, return_value=([], ["site:q"])),
        patch("research_loop.expand_queries") as mock_expand,
        patch("research_loop.extract_facts", new_callable=AsyncMock, return_value=rich_facts),
        patch("research_loop.verify_and_review", return_value=(rich_facts, MagicMock(
            corroborated=1, boosted=0, demoted=0, removed_by_review=0, follow_up_queries=[],
        ))),
        patch("research_loop.synthesize_report", new_callable=AsyncMock) as mock_synth,
        patch("research_loop.generate_report") as mock_report,
        patch("research_loop.config.router_enabled", True),
        patch("research_loop.config.research_max_hops", 1),
        patch("research_loop.config.research_max_router_calls", 2),
        patch("research_loop.config.research_coverage_threshold", 0.65),
        patch("research_loop.config.min_unique_domains_target", 3),
    ):
        from models import ReportSynthesis

        mock_synth.return_value = ReportSynthesis(executive_summary="Summary.")
        mock_report.return_value = MagicMock(slug="test-slug", citations=[1, 2])
        from query_expand import ExpandResult

        mock_expand.return_value = ExpandResult(queries=[], capped=False)

        events: list[str] = []

        async def emit(event_type: str, data: dict):
            events.append(event_type)

        report = await run_research_loop(request, event_callback=emit)

    assert "source_router_decision" in events
    assert "coverage_eval" in events
    assert report.slug == "test-slug"
    print("test_research_loop_completes_with_mocks: PASS")


async def _test_research_loop_wires_gap_hints_to_next_hop():
    """Gap → expand → next hop gets pending site/open + preferred source ids."""
    request = ResearchRequest(
        topic="European corporate direct lending fundraising trends 2026",
        max_sources=10,
    )
    thin_facts = [
        _fact("European fundraising rebounded in 2025.", "https://a.com/1"),
    ]
    decision_hop0 = RouterDecision(
        selected_source_ids=["stepstone_insights"],
        site_queries=["site:stepstonegroup.com direct lending"],
        rationale="hop0",
        defer_open_web=True,
    )
    decision_hop1 = RouterDecision(
        selected_source_ids=["other_id"],
        site_queries=["site:other.com filler"],
        rationale="hop1",
        defer_open_web=True,
    )
    route_mock = AsyncMock(side_effect=[decision_hop0, decision_hop1])
    execute_mock = AsyncMock(
        side_effect=[
            (
                [SearchResult(url="https://a.com/1", title="A", snippet="s", full_text="body")],
                ["site:stepstonegroup.com direct lending"],
            ),
            (
                [SearchResult(url="https://b.com/2", title="B", snippet="s", full_text="body")],
                ["site:pei.com European private debt fundraising", "open q"],
            ),
        ]
    )

    from query_expand import ExpandResult, ExpandedQuery

    def fake_expand(topic, gap_hints, candidates, max_queries=None, hop=0, facts=None, **_kwargs):
        queries = []
        for h in gap_hints:
            queries.append(
                ExpandedQuery(
                    query=f"site:pei.com {h.dimension}",
                    research_goal=h.research_goal,
                    channel="site",
                    template_id="t-site",
                    dimension=h.dimension,
                )
            )
            queries.append(
                ExpandedQuery(
                    query=f"{h.dimension} European private debt fundraising 2026",
                    research_goal=h.research_goal,
                    channel="open",
                    template_id="t-open",
                    dimension=h.dimension,
                )
            )
        return ExpandResult(queries=queries, capped=False)

    coverage_payloads: list[dict] = []
    execute_kwargs: list[dict] = []

    async def emit(event_type: str, data: dict):
        if event_type == "coverage_eval":
            coverage_payloads.append(data)

    async def execute_side_effect(*args, **kwargs):
        execute_kwargs.append(kwargs)
        return await execute_mock(*args, **kwargs)

    with (
        patch("research_loop.route_sources", route_mock),
        patch("research_loop.execute_router_decision", side_effect=execute_side_effect),
        patch("research_loop.expand_queries", side_effect=fake_expand),
        patch("research_loop.extract_facts", new_callable=AsyncMock, return_value=thin_facts),
        patch("research_loop.verify_and_review", return_value=(thin_facts, MagicMock(
            corroborated=0, boosted=0, demoted=0, removed_by_review=0, follow_up_queries=[],
        ))),
        patch("research_loop.synthesize_report", new_callable=AsyncMock) as mock_synth,
        patch("research_loop.generate_report") as mock_report,
        patch("research_loop.config.router_enabled", True),
        patch("research_loop.config.research_max_hops", 2),
        patch("research_loop.config.research_max_router_calls", 4),
        patch("research_loop.config.research_coverage_threshold", 0.65),
        patch("research_loop.config.min_unique_domains_target", 3),
        patch("research_loop.config.router_max_site_queries", 5),
        patch("research_loop.config.router_max_sources_per_round", 6),
        patch(
            "research_loop.filter_candidates",
            return_value=[
                MagicMock(id="pei"),
                MagicMock(id="preqin_insights"),
                MagicMock(id="stepstone_insights"),
                MagicMock(id="other_id"),
            ],
        ),
    ):
        from models import ReportSynthesis

        mock_synth.return_value = ReportSynthesis(executive_summary="Summary.")
        mock_report.return_value = MagicMock(slug="gap-slug", citations=[])

        await run_research_loop(request, event_callback=emit)

    assert coverage_payloads
    assert coverage_payloads[0]["should_continue"] is True
    gap0 = coverage_payloads[0]["gap_hints"]
    assert any(h.get("suggested_queries") for h in gap0)

    assert len(execute_kwargs) >= 2
    hop1 = execute_kwargs[1]
    assert hop1.get("open_queries")
    assert any("fundraising" in q.lower() for q in (hop1.get("open_queries") or []))

    # Preferred catalog ids + pending site queries applied on hop-1 decision.
    second_decision = execute_mock.call_args_list[1].args[1]
    assert second_decision.selected_source_ids[0] == "pei"
    assert any("pei.com" in q for q in second_decision.site_queries)
    print("test_research_loop_wires_gap_hints_to_next_hop: PASS")


async def _test_research_loop_event_chain_with_real_expand():
    """Step 50: full SSE chain using real expand_queries (I/O mocked only)."""
    request = ResearchRequest(
        topic="European corporate direct lending fundraising trends 2026",
        max_sources=10,
    )
    thin_facts = [
        _fact("European fundraising rebounded in 2025.", "https://a.com/1"),
    ]
    rich_facts = [
        _fact("European fundraising rebounded in 2025.", "https://a.com/1"),
        _fact("Direct lending volumes within norms; refinancings share.", "https://b.com/2"),
        _fact("Gross yields 9-10%; spreads tightened.", "https://c.com/3"),
        _fact("Defaults below historical averages.", "https://d.com/4"),
        _fact("ELTIF evergreen product launch Europe.", "https://e.com/5"),
        _fact("Premium vs leveraged loans and high yield.", "https://f.com/6"),
    ]

    decisions = [
        RouterDecision(
            selected_source_ids=["stepstone_insights"],
            site_queries=["site:stepstonegroup.com direct lending"],
            rationale="hop0",
            defer_open_web=True,
        ),
        RouterDecision(
            selected_source_ids=["other_id"],
            site_queries=["site:other.com filler"],
            rationale="hop1",
            defer_open_web=True,
        ),
    ]
    route_mock = AsyncMock(side_effect=decisions)

    extract_calls = {"n": 0}

    async def fake_extract(topic, results):
        extract_calls["n"] += 1
        return thin_facts if extract_calls["n"] == 1 else rich_facts

    def fake_verify(topic, facts):
        # Second hop returns rich facts so coverage can stop.
        out = rich_facts if extract_calls["n"] >= 2 else facts
        return out, MagicMock(
            corroborated=0, boosted=0, demoted=0, removed_by_review=0, follow_up_queries=[],
        )

    execute_mock = AsyncMock(
        side_effect=[
            (
                [SearchResult(url="https://a.com/1", title="A", snippet="s", full_text="body")],
                ["site:stepstonegroup.com direct lending"],
            ),
            (
                [
                    SearchResult(url="https://b.com/2", title="B", snippet="s", full_text="body"),
                    SearchResult(url="https://c.com/3", title="C", snippet="s", full_text="body"),
                    SearchResult(url="https://d.com/4", title="D", snippet="s", full_text="body"),
                ],
                ["site:privateequityinternational.com …", "open fundraising"],
            ),
        ]
    )

    events: list[tuple[str, dict]] = []

    async def emit(event_type: str, data: dict):
        events.append((event_type, data))

    candidates = [
        _candidate("pei", "privateequityinternational.com"),
        _candidate("preqin_insights", "preqin.com"),
        _candidate("stepstone_insights", "stepstonegroup.com"),
        _candidate("fnlondon", "fnlondon.com"),
        _candidate("other_id", "other.com"),
    ]

    with (
        patch("research_loop.route_sources", route_mock),
        patch("research_loop.execute_router_decision", execute_mock),
        patch("research_loop.extract_facts", side_effect=fake_extract),
        patch("research_loop.verify_and_review", side_effect=fake_verify),
        patch("research_loop.synthesize_report", new_callable=AsyncMock) as mock_synth,
        patch("research_loop.generate_report") as mock_report,
        patch("research_loop.filter_candidates", return_value=candidates),
        patch("research_loop.config.router_enabled", True),
        patch("research_loop.config.research_max_hops", 3),
        patch("research_loop.config.research_max_router_calls", 4),
        patch("research_loop.config.research_coverage_threshold", 0.65),
        patch("research_loop.config.min_unique_domains_target", 3),
        patch("research_loop.config.router_max_site_queries", 5),
        patch("research_loop.config.router_max_sources_per_round", 6),
        patch("research_loop.config.query_expand_max_per_hop", 6),
    ):
        from models import ReportSynthesis

        mock_synth.return_value = ReportSynthesis(executive_summary="Summary.")
        mock_report.return_value = MagicMock(slug="chain-slug", citations=[1])

        report = await run_research_loop(request, event_callback=emit)

    names = [e for e, _ in events]
    assert names[0] == "search_start"
    assert "catalog_filtered" in names
    assert names.count("source_router_decision") >= 2
    assert "coverage_eval" in names
    assert "query_expand" in names
    assert "report_complete" in names

    # Event order: first coverage_eval before query_expand; expand before second router.
    idx_cov0 = names.index("coverage_eval")
    idx_expand = names.index("query_expand")
    idx_router1 = [i for i, n in enumerate(names) if n == "source_router_decision"][1]
    assert idx_cov0 < idx_expand < idx_router1

    expand_payload = next(d for n, d in events if n == "query_expand")
    assert expand_payload["query_count"] >= 1
    channels = {q["channel"] for q in expand_payload["queries"]}
    assert "site" in channels or "open" in channels

    hop1_kwargs = execute_mock.call_args_list[1].kwargs
    assert hop1_kwargs.get("gap_hop") is True
    assert hop1_kwargs.get("open_queries")
    assert hop1_kwargs.get("missing_dimensions")

    cov0 = next(d for n, d in events if n == "coverage_eval")
    assert cov0["should_continue"] is True
    assert any(h.get("suggested_queries") for h in cov0["gap_hints"])

    assert report.slug == "chain-slug"
    print("test_research_loop_event_chain_with_real_expand: PASS")


async def _test_research_loop_stops_when_stagnant():
    """Two hops with zero new facts → stagnant_hops stops further expand."""
    request = ResearchRequest(
        topic="European corporate direct lending fundraising trends 2026",
        max_sources=10,
    )
    decision = RouterDecision(
        selected_source_ids=["stepstone_insights"],
        site_queries=["site:stepstonegroup.com x"],
        defer_open_web=True,
    )
    route_mock = AsyncMock(return_value=decision)
    execute_mock = AsyncMock(
        return_value=(
            [SearchResult(url="https://a.com/1", title="A", snippet="s", full_text="body")],
            ["site:q"],
        )
    )

    expand_calls = {"n": 0}

    def counting_expand(*args, **kwargs):
        from query_expand import ExpandResult, ExpandedQuery

        expand_calls["n"] += 1
        return ExpandResult(
            queries=[
                ExpandedQuery(
                    query="site:pei.com fundraising",
                    research_goal="g",
                    channel="site",
                    template_id="t",
                    dimension="fundraising",
                ),
                ExpandedQuery(
                    query="open fundraising",
                    research_goal="g",
                    channel="open",
                    template_id="t",
                    dimension="fundraising",
                ),
            ],
            capped=False,
        )

    async def fresh_thin(_topic, _results):
        # New list each call — avoid mutating a shared mock return_value list.
        return [_fact("European fundraising rebounded.", "https://a.com/1")]

    def fresh_verify(_topic, facts):
        out = [_fact("European fundraising rebounded.", "https://a.com/1")]
        return out, MagicMock(
            corroborated=0, boosted=0, demoted=0, removed_by_review=0, follow_up_queries=[],
        )

    with (
        patch("research_loop.route_sources", route_mock),
        patch("research_loop.execute_router_decision", execute_mock),
        patch("research_loop.expand_queries", side_effect=counting_expand),
        patch("research_loop.extract_facts", side_effect=fresh_thin),
        patch("research_loop.verify_and_review", side_effect=fresh_verify),
        patch("research_loop.synthesize_report", new_callable=AsyncMock) as mock_synth,
        patch("research_loop.generate_report") as mock_report,
        patch(
            "research_loop.filter_candidates",
            return_value=[_candidate("pei", "privateequityinternational.com")],
        ),
        patch("research_loop.config.router_enabled", True),
        patch("research_loop.config.research_max_hops", 5),
        patch("research_loop.config.research_max_router_calls", 6),
        patch("research_loop.config.research_coverage_threshold", 0.65),
        patch("research_loop.config.min_unique_domains_target", 3),
    ):
        from models import ReportSynthesis

        mock_synth.return_value = ReportSynthesis(executive_summary="S")
        mock_report.return_value = MagicMock(slug="stagnant", citations=[])

        await run_research_loop(request, event_callback=None)

    # Hop0: facts 0→1 → expand. Hop1/2: unchanged count raises stagnant;
    # one more execute may run before stagnant=2 is observed at evaluate time.
    assert expand_calls["n"] <= 3
    assert execute_mock.await_count <= 4
    print("test_research_loop_stops_when_stagnant: PASS")


if __name__ == "__main__":
    asyncio.run(_test_research_loop_completes_with_mocks())
    asyncio.run(_test_research_loop_wires_gap_hints_to_next_hop())
    asyncio.run(_test_research_loop_event_chain_with_real_expand())
    asyncio.run(_test_research_loop_stops_when_stagnant())
    print("All research loop tests passed!")
