"""Unit tests for per-source extraction."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from extraction import (
    extract_facts,
    extract_facts_from_source,
    _normalize_signal_type,
    _parse_facts_json,
    _to_extracted_facts,
)
from models import ExtractedFact, SearchResult


def test_parse_facts_json_with_fences():
    raw = '```json\n[{"fact": "a", "quoted_text": "b", "confidence": "high"}]\n```'
    parsed = _parse_facts_json(raw)
    assert len(parsed) == 1
    assert parsed[0]["fact"] == "a"


def test_normalize_signal_type():
    assert _normalize_signal_type("fundraise") == "fundraise"
    assert _normalize_signal_type("Fund-Raise") == "fundraise"
    assert _normalize_signal_type("bogus") == "other"
    assert _normalize_signal_type(None) == "other"


def test_to_extracted_facts_signal_types():
    source = SearchResult(
        url="https://example.com",
        title="Example",
        snippet="",
        full_text="text",
    )
    facts = _to_extracted_facts(
        [
            {
                "fact": "Fundraising rebounded",
                "quoted_text": "fundraising rebounded in 2025",
                "confidence": "high",
                "signal_type": "fundraise",
                "entity_type": "fund",
            },
            {
                "fact": "Something vague",
                "quoted_text": "vague text here",
                "confidence": "low",
                "signal_type": "not_a_real_type",
            },
        ],
        source,
    )
    assert facts[0].signal_type == "fundraise"
    assert facts[0].entity_type == "fund"
    assert facts[1].signal_type == "other"
    assert facts[1].entity_type == "other"


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

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("extraction.get_openai_client", return_value=mock_client):
        facts = await extract_facts_from_source("Python history", source)

    assert len(facts) == 1
    assert facts[0].source_url == "https://example.com"
    assert facts[0].source_title == "Example"
    assert facts[0].signal_type == "other"
    mock_client.chat.completions.create.assert_awaited_once()


async def _test_investor_prompt_uses_signal_types():
    source = SearchResult(
        url="https://example.com/pd",
        title="PD",
        snippet="",
        full_text="European fundraising rebounded in 2025.",
    )
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    '[{"fact": "European fundraising rebounded", '
                    '"quoted_text": "fundraising rebounded in 2025", '
                    '"confidence": "high", "signal_type": "fundraise", '
                    '"entity_type": "fund"}]'
                )
            )
        )
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("extraction.get_openai_client", return_value=mock_client):
        facts = await extract_facts_from_source(
            "European corporate direct lending fundraising trends 2026",
            source,
        )

    prompt = mock_client.chat.completions.create.await_args.kwargs["messages"][0]["content"]
    assert "signal_type" in prompt
    assert "fundraise" in prompt
    assert facts[0].signal_type == "fundraise"


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
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        with patch("extraction.get_openai_client", return_value=mock_client):
            facts = await extract_facts_from_source("topic", source)
            mock_client.chat.completions.create.assert_not_awaited()
        assert facts == []

    asyncio.run(run())


if __name__ == "__main__":
    test_parse_facts_json_with_fences()
    test_normalize_signal_type()
    test_to_extracted_facts_signal_types()
    asyncio.run(_test_extract_facts_from_source())
    asyncio.run(_test_investor_prompt_uses_signal_types())
    asyncio.run(_test_extract_facts_concurrent_per_source())
    test_skips_failed_fetch()
    print("test_extraction_unit: PASS")
