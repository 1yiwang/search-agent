"""Tests for coverage evaluator."""
from models import ExtractedFact
from coverage import evaluate_coverage


def _fact(text: str) -> ExtractedFact:
    return ExtractedFact(
        fact=text,
        source_url="https://example.com",
        source_title="Example",
        quoted_text=text,
        confidence="high",
    )


def test_coverage_high_when_all_dimensions():
    facts = [
        _fact("European fundraising rebounded in 2025 while US weakened."),
        _fact("Direct lending volumes within norms; LBO constrained; refinancings share volume."),
        _fact("Gross yields remain 9-10%; spreads tightened."),
        _fact("Defaults rose but remain below historical averages; leverage stable."),
        _fact("StepStone ELTIF evergreen BDC product launch in Europe."),
        _fact("Direct lending premium versus leveraged loans and high yield."),
    ]
    topic = "European corporate direct lending fundraising trends 2026"
    result = evaluate_coverage(
        topic, facts, hop=0, max_hops=3, coverage_threshold=0.65,
        sources_budget_remaining=5, stagnant_hops=0,
    )
    assert result.score >= 0.65
    assert not result.should_continue
    print("test_coverage_high_when_all_dimensions: PASS")


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
    print("All coverage tests passed!")
