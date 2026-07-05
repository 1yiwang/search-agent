"""Unit tests for cross-source verifier."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from models import ExtractedFact
from verifier import (
    apply_review,
    verify_cross_source,
    verify_and_review,
)


def _fact(text: str, url: str, confidence: str = "medium") -> ExtractedFact:
    return ExtractedFact(
        fact=text,
        source_url=url,
        source_title="Source",
        quoted_text=f"Quote for {text}",
        confidence=confidence,
    )


def test_verify_boosts_corroborated_facts():
    facts = [
        _fact("Python 3.12 adds improved error messages", "https://a.com", "medium"),
        _fact("Python 3.12 adds improved error messages", "https://b.com", "low"),
    ]
    verified, stats = verify_cross_source(facts, similarity_threshold=0.8)

    assert stats.corroborated == 2
    assert stats.boosted >= 1
    assert all(f.confidence in ("medium", "high") for f in verified)


def test_verify_demotes_uncorroborated_high():
    facts = [_fact("Some claim without backup", "https://only.com", "high")]
    verified, stats = verify_cross_source(facts)

    assert verified[0].confidence == "medium"
    assert stats.demoted == 1


def test_apply_review_removes_indices():
    facts = [_fact("keep", "https://a.com"), _fact("remove", "https://b.com")]
    result = apply_review(facts, [1])
    assert len(result) == 1
    assert result[0].fact == "keep"


async def _test_verify_and_review_applies_llm_removal():
    facts = [
        _fact("Valid fact about EU AI Act scope", "https://a.com"),
        _fact("Buy cheap SEO pills now", "https://spam.com"),
    ]

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"remove_indices": [1], "notes": "removed spam", "follow_up_queries": []}'))
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("verifier.get_openai_client", return_value=mock_client):
        verified, stats = await verify_and_review("EU AI Act", facts, max_revisions=1)

    assert len(verified) == 1
    assert "SEO" not in verified[0].fact
    assert stats.removed_by_review == 1


if __name__ == "__main__":
    test_verify_boosts_corroborated_facts()
    test_verify_demotes_uncorroborated_high()
    test_apply_review_removes_indices()
    asyncio.run(_test_verify_and_review_applies_llm_removal())
    print("test_verifier: PASS")
