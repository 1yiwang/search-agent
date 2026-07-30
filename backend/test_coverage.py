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
        min_unique_domains=3,
    )
    assert result.unique_domains == 1
    assert not result.source_diversity_ok
    assert result.should_continue
    print("test_coverage_continue_when_low_diversity: PASS")


def test_coverage_diversity_uses_explicit_threshold():
    facts = [
        _fact("European fundraising rebounded.", "https://a.com/1"),
        _fact("Direct lending volumes rose.", "https://b.com/2"),
    ]
    topic = "European corporate direct lending fundraising trends 2026"
    ok_at_2 = evaluate_coverage(
        topic, facts, hop=0, max_hops=3, coverage_threshold=0.99,
        sources_budget_remaining=10, stagnant_hops=0,
        min_unique_domains=2,
    )
    need_3 = evaluate_coverage(
        topic, facts, hop=0, max_hops=3, coverage_threshold=0.99,
        sources_budget_remaining=10, stagnant_hops=0,
        min_unique_domains=3,
    )
    assert ok_at_2.source_diversity_ok
    assert not need_3.source_diversity_ok
    print("test_coverage_diversity_uses_explicit_threshold: PASS")


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
    assert result.gap_hints
    assert result.gap_hints[0].research_goal
    print("test_coverage_continue_when_gaps: PASS")


def test_coverage_signal_type_fills_gap():
    """Signal types alone can cover a dimension even with weak keyword text."""
    facts = [
        ExtractedFact(
            fact="European activity strengthened last year versus peers.",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="activity strengthened",
            confidence="high",
            signal_type="fundraise",
        ),
        ExtractedFact(
            fact="Deal mix stayed within historical norms.",
            source_url="https://b.com/2",
            source_title="B",
            quoted_text="within historical norms",
            confidence="high",
            signal_type="deployment",
        ),
        ExtractedFact(
            fact="Pricing stayed attractive versus liquid credit.",
            source_url="https://c.com/3",
            source_title="C",
            quoted_text="pricing stayed attractive",
            confidence="medium",
            signal_type="spread_market",
        ),
        ExtractedFact(
            fact="Credit quality showed contained stress.",
            source_url="https://d.com/4",
            source_title="D",
            quoted_text="contained stress",
            confidence="medium",
            signal_type="default_distress",
        ),
        ExtractedFact(
            fact="A new evergreen vehicle was announced.",
            source_url="https://e.com/5",
            source_title="E",
            quoted_text="evergreen vehicle",
            confidence="high",
            signal_type="product_launch",
        ),
    ]
    topic = "European corporate direct lending fundraising trends 2026"
    result = evaluate_coverage(
        topic, facts, hop=0, max_hops=3, coverage_threshold=0.65,
        sources_budget_remaining=5, stagnant_hops=0,
    )
    assert "fundraising" in result.covered_dimensions
    assert "product_evergreen" in result.covered_dimensions
    assert "credit_risk" in result.covered_dimensions
    assert result.score >= 0.65
    print("test_coverage_signal_type_fills_gap: PASS")


def test_general_topic_empty_facts_continues():
    topic = "European AI short video platform ranking H1 2026"
    result = evaluate_coverage(
        topic, [], hop=0, max_hops=3, coverage_threshold=0.65,
        sources_budget_remaining=10, stagnant_hops=0,
    )
    assert result.score == 0.0
    assert result.should_continue is True
    assert any(h.dimension == "_empty" for h in result.gap_hints)
    print("test_general_topic_empty_facts_continues: PASS")


def test_general_topic_enough_facts_can_stop():
    topic = "European AI short video platforms"
    # 3 facts is no longer enough — must continue
    few = [
        _fact("Platform A leads Europe in AI short video MAU.", "https://a.com/1"),
        _fact("Platform B raised a Series B in Berlin.", "https://b.com/2"),
        _fact("Market share shifted toward generative tools.", "https://c.com/3"),
    ]
    thin = evaluate_coverage(
        topic, few, hop=0, max_hops=5, coverage_threshold=0.65,
        sources_budget_remaining=20, stagnant_hops=0,
        min_unique_domains=3,
    )
    assert thin.should_continue is True

    many = [
        _fact(
            f"Case study {i}: expert analysts note challenges and market share in Europe.",
            f"https://d{i}.com/{i}",
        )
        for i in range(8)
    ]
    result = evaluate_coverage(
        topic, many, hop=0, max_hops=5, coverage_threshold=0.65,
        sources_budget_remaining=20, stagnant_hops=0,
        min_unique_domains=5,
    )
    assert result.score > 0
    assert result.unique_domains >= 5
    assert not result.should_continue  # 8 facts + 5 domains + synthesis gates
    print("test_general_topic_enough_facts_can_stop: PASS")


if __name__ == "__main__":
    test_coverage_high_when_all_dimensions()
    test_coverage_continue_when_gaps()
    test_coverage_continue_when_low_diversity()
    test_coverage_diversity_uses_explicit_threshold()
    test_coverage_signal_type_fills_gap()
    test_general_topic_empty_facts_continues()
    test_general_topic_enough_facts_can_stop()
    print("All coverage tests passed!")
