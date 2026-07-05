"""Unit tests for multi-hop follow-up research."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from models import ExtractedFact
from multihop import finalize_facts


def _fact(text: str, url: str = "https://a.com") -> ExtractedFact:
    return ExtractedFact(
        fact=text,
        source_url=url,
        source_title="Source",
        quoted_text=f"Quote: {text}",
        confidence="medium",
    )


async def _test_finalize_facts_runs_follow_up_hop():
    facts = [_fact("Initial fact about EU AI Act")]
    seen_urls = {"a.com"}
    topics: list[str] = ["EU AI Act"]
    events = []

    async def emit(event_type: str, data: dict):
        events.append((event_type, data))

    stats_follow_up = type("S", (), {
        "corroborated": 0,
        "boosted": 0,
        "demoted": 0,
        "removed_by_review": 0,
        "follow_up_queries": [],
        "review_notes": "",
        "total": 2,
    })()

    stats_with_gap = type("S", (), {
        "corroborated": 0,
        "boosted": 0,
        "demoted": 0,
        "removed_by_review": 0,
        "follow_up_queries": ["EU AI Act penalties 2026"],
        "review_notes": "need penalties",
        "total": 1,
    })()

    with (
        patch("multihop.verify_and_review", new_callable=AsyncMock) as mock_verify,
        patch("multihop._fetch_follow_up_facts", new_callable=AsyncMock) as mock_fetch,
    ):
        mock_verify.side_effect = [
            (facts, stats_with_gap),
            (facts + [_fact("Penalty details", "https://b.com")], stats_follow_up),
        ]
        mock_fetch.return_value = [_fact("Penalty details", "https://b.com")]

        result, stats = await finalize_facts(
            "EU AI Act",
            facts,
            seen_urls,
            topics,
            sources_per_query=2,
            emit=emit,
        )

    assert len(result) == 2
    assert mock_fetch.await_count == 1
    assert "EU AI Act penalties 2026" in topics
    assert any(e[0] == "multihop_start" for e in events)
    assert any(e[0] == "multihop_complete" for e in events)
    assert stats.follow_up_queries == []


async def _test_finalize_facts_stops_at_max_hops():
    facts = [_fact("Only fact")]
    seen_urls: set[str] = set()
    topics: list[str] = []

    gap_stats = MagicMock()
    gap_stats.corroborated = 0
    gap_stats.boosted = 0
    gap_stats.demoted = 0
    gap_stats.removed_by_review = 0
    gap_stats.follow_up_queries = ["gap query"]
    gap_stats.review_notes = ""
    gap_stats.total = 1

    async def emit(_event_type: str, _data: dict):
        pass

    with (
        patch("multihop.config") as mock_config,
        patch("multihop.verify_and_review", new_callable=AsyncMock) as mock_verify,
        patch("multihop._fetch_follow_up_facts", new_callable=AsyncMock) as mock_fetch,
    ):
        mock_config.multihop_max_hops = 1
        mock_config.multihop_sources_per_query = 2
        mock_verify.return_value = (facts, gap_stats)
        mock_fetch.return_value = [_fact("Hop fact", "https://c.com")]

        await finalize_facts("topic", facts, seen_urls, topics, 2, emit)

    assert mock_fetch.await_count == 1


if __name__ == "__main__":
    asyncio.run(_test_finalize_facts_runs_follow_up_hop())
    asyncio.run(_test_finalize_facts_stops_at_max_hops())
    print("test_multihop: PASS")
