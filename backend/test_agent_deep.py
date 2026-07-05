"""Unit tests for deep research parallel dimensions (mocked search)."""
import asyncio
from unittest.mock import AsyncMock, patch

from models import ResearchDimension, ResearchPlan, SearchResult
from agent import _research_dimension, run_deep_research


def _result(url: str) -> SearchResult:
    return SearchResult(
        url=url,
        title=f"Title {url}",
        snippet="snippet",
        full_text="Some factual content about the topic.",
    )


async def _test_research_dimension_parallel_queries():
    dim = ResearchDimension(
        title="Scope",
        queries=["query A", "query B"],
        priority=1,
    )
    events = []

    async def emit(event_type: str, data: dict):
        events.append((event_type, data))

    with patch("agent.search_and_fetch", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = [
            [_result("https://a.com")],
            [_result("https://b.com")],
        ]
        _, results = await _research_dimension(dim, sources_per_query=2, emit=emit)

    assert len(results) == 2
    assert mock_search.await_count == 2
    assert events[0][0] == "dimension_start"
    assert events[-1][0] == "dimension_complete"


async def _test_run_deep_research_merges_dimensions():
    plan = ResearchPlan(
        topic="EU AI Act",
        title="EU AI Act Report",
        date="2026-07-05",
        dimensions=[
            ResearchDimension(title="Scope", queries=["q1"], priority=1),
            ResearchDimension(title="Impact", queries=["q2"], priority=2),
        ],
        max_sections=5,
    )

    with (
        patch("agent._research_dimension", new_callable=AsyncMock) as mock_dim,
        patch("agent.extract_facts", new_callable=AsyncMock) as mock_extract,
        patch("agent.finalize_facts", new_callable=AsyncMock) as mock_finalize,
        patch("agent.generate_report") as mock_report,
    ):
        mock_dim.side_effect = [
            (plan.dimensions[0], [_result("https://a.com")]),
            (plan.dimensions[1], [_result("https://b.com")]),
        ]
        mock_extract.return_value = []
        mock_finalize.return_value = ([], type("S", (), {
            "corroborated": 0, "boosted": 0, "demoted": 0,
            "removed_by_review": 0, "follow_up_queries": [],
        })())

        from models import ResearchReport, ReportMetadata

        mock_report.return_value = ResearchReport(
            topic="EU AI Act Report",
            slug="eu-ai-act-report",
            metadata=ReportMetadata(
                execution_time_seconds=1.0,
                source_count=0,
                topics_searched=[],
                started_at="2026-07-05T00:00:00+00:00",
                completed_at="2026-07-05T00:00:01+00:00",
            ),
        )

        report = await run_deep_research(plan, sources_per_query=2)

    assert mock_dim.await_count == 2
    assert mock_extract.await_count == 2
    assert report.slug == "eu-ai-act-report"
    assert report.metadata.topics_searched == ["q1", "q2"]


if __name__ == "__main__":
    asyncio.run(_test_research_dimension_parallel_queries())
    asyncio.run(_test_run_deep_research_merges_dimensions())
    print("test_agent_deep: PASS")
