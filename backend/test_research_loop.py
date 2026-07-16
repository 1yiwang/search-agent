"""Tests for coverage-driven research loop (mocked I/O)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from models import ExtractedFact, ResearchRequest
from research_loop import run_research_loop
from sources.models import RouterDecision


def _fact(text: str) -> ExtractedFact:
    return ExtractedFact(
        fact=text,
        source_url="https://stepstonegroup.com/a",
        source_title="StepStone",
        quoted_text=text,
        confidence="high",
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
        _fact("European fundraising rebounded in 2025."),
        _fact("Direct lending volumes within norms; refinancings share."),
        _fact("Gross yields 9-10%; spreads tightened."),
        _fact("Defaults below historical averages."),
        _fact("ELTIF evergreen product launch Europe."),
        _fact("Premium vs leveraged loans and high yield."),
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


if __name__ == "__main__":
    asyncio.run(_test_research_loop_completes_with_mocks())
    print("All research loop tests passed!")
