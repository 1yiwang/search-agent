"""Unit tests for per-source extraction."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from extraction import extract_facts, extract_facts_from_source, _parse_facts_json
from models import ExtractedFact, SearchResult


def test_parse_facts_json_with_fences():
    raw = '```json\n[{"fact": "a", "quoted_text": "b", "confidence": "high"}]\n```'
    parsed = _parse_facts_json(raw)
    assert len(parsed) == 1
    assert parsed[0]["fact"] == "a"


async def _test_extract_facts_from_source():
    source = SearchResult(
        url="https://example.com",
        title="Example",
        snippet="snippet",
        full_text="Python was released in 1991 by Guido van Rossum.",
    )
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='[{"fact": "Python was released in 1991", "quoted_text": "released in 1991", "confidence": "high"}]'
            )
        )
    ]

    with patch("extraction.client.chat.completions.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        facts = await extract_facts_from_source("Python history", source)

    assert len(facts) == 1
    assert facts[0].source_url == "https://example.com"
    assert facts[0].source_title == "Example"
    mock_create.assert_awaited_once()


async def _test_extract_facts_concurrent_per_source():
    sources = [
        SearchResult(url=f"https://example.com/{i}", title=f"S{i}", snippet="", full_text=f"fact {i}")
        for i in range(4)
    ]
    call_count = 0

    async def fake_extract(topic, source):
        nonlocal call_count
        call_count += 1
        return [
            ExtractedFact(
                fact=f"fact from {source.url}",
                source_url=source.url,
                source_title=source.title,
                quoted_text="quoted",
                confidence="medium",
            )
        ]

    with patch("extraction.extract_facts_from_source", side_effect=fake_extract):
        facts = await extract_facts("topic", sources)

    assert call_count == 4
    assert len(facts) == 4
    assert {f.source_url for f in facts} == {s.url for s in sources}


def test_skips_failed_fetch():
    async def run():
        source = SearchResult(
            url="https://bad.com",
            title="Bad",
            snippet="",
            full_text="[Failed to fetch https://bad.com: 403]",
        )
        with patch("extraction.client.chat.completions.create", new_callable=AsyncMock) as mock_create:
            facts = await extract_facts_from_source("topic", source)
            mock_create.assert_not_awaited()
        assert facts == []

    asyncio.run(run())


if __name__ == "__main__":
    test_parse_facts_json_with_fences()
    asyncio.run(_test_extract_facts_from_source())
    asyncio.run(_test_extract_facts_concurrent_per_source())
    test_skips_failed_fetch()
    print("test_extraction_unit: PASS")
