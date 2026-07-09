"""Tests for coverage evaluator."""
from models import ExtractedFact
from coverage import evaluate_coverage


def _fact(text: str, url: str = "https://example.com") -> ExtractedFact:
    return ExtractedFact(
        fact=text,
        source_url=url,
        source_title="Example",
        quoted_text=text,
        confidence="high",
    )


def test_coverage_high_when_all_dimensions():
    facts = [
        _fact("European fundraising rebounded in 2025 while US weakened.", "https://a.com/r1"),
        _fact("Direct lending volumes within norms; LBO constrained; refinancings share volume.", "https://b.com/r2"),
        _fact("Gross yields remain 9-10%; spreads tightened.", "https://c.com/r3"),
        _fact("Defaults rose but remain below historical averages; leverage stable.", "https://d.com/r4"),
        _fact("StepStone ELTIF evergreen BDC product launch in Europe.", "https://e.com/r5"),
        _fact("Direct lending premium versus leveraged loans and high yield.", "https://f.com/r6"),
    ]
    topic = "European corporate direct lending fundraising trends 2026"
    result = evaluate_coverage(
        topic, facts, hop=0, max_hops=3, coverage_threshold=0.65,
        sources_budget_remaining=5, stagnant_hops=0,
    )
    assert result.score >= 0.65
    assert result.source_diversity_ok
    assert not result.should_continue
    print("test_coverage_high_when_all_dimensions: PASS")


def test_coverage_continue_when_low_diversity():
    facts = [
        _fact("European fundraising rebounded in 2025 while US weakened."),
        _fact("Direct lending volumes within norms; LBO constrained."),
    ]
    topic = "European corporate direct lending fundraising trends 2026"
    result = evaluate_coverage(
        topic, facts, hop=0, max_hops=3, coverage_threshold=0.65,
        sources_budget_remaining=10, stagnant_hops=0,
    )
    assert result.unique_domains == 1
    assert not result.source_diversity_ok
    assert result.should_continue
    print("test_coverage_continue_when_low_diversity: PASS")


def test_coverage_continue_when_gaps():
    facts = [_fact("European fundraising rebounded in 2025.")]
    topic = "European corporate direct lending fundraising trends 2026"
    result = evaluate_coverage(
        topic, facts, hop=0, max_hops=3, coverage_threshold=0.65,
        sources_budget_remaining=10, stagnant_hops=0,
    )
    assert result.score < 0.65
    assert result.should_continue
    assert result.suggested_router_hints
    print("test_coverage_continue_when_gaps: PASS")


if __name__ == "__main__":
    test_coverage_high_when_all_dimensions()
    test_coverage_continue_when_gaps()
    test_coverage_continue_when_low_diversity()
    print("All coverage tests passed!")
