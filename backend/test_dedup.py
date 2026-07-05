"""Smoke test for deduplication."""
from dedup import deduplicate_facts, deduplicate_search_results
from models import ExtractedFact, SearchResult


def test_url_dedup():
    results = [
        SearchResult(url="https://www.example.com/page", title="A", snippet="x"),
        SearchResult(url="https://example.com/page/", title="A", snippet="x"),
        SearchResult(url="https://other.com/page", title="B", snippet="y"),
    ]
    deduped = deduplicate_search_results(results)
    assert len(deduped) == 2, f"Expected 2, got {len(deduped)}"
    print("test_url_dedup: PASS")


def test_fact_dedup():
    facts = [
        ExtractedFact(
            fact="Python was created in 1991",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="created in 1991",
            confidence="high",
        ),
        ExtractedFact(
            fact="Python was created in 1991 by Guido",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="created in 1991 by Guido",
            confidence="medium",
        ),
        ExtractedFact(
            fact="Python emphasizes readability",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="emphasizes readability",
            confidence="high",
        ),
    ]
    deduped = deduplicate_facts(facts)
    # First two are similar (same URL), third is different
    assert len(deduped) == 2, f"Expected 2, got {len(deduped)}"
    print("test_fact_dedup: PASS")


if __name__ == "__main__":
    test_url_dedup()
    test_fact_dedup()
    print("All dedup tests passed!")
