"""Unit tests for watchlist delta comparison (Step 41c)."""
from models import ExtractedFact, ResearchReport, StructuredFinding
from watchlist.delta import compare_reports


def _report(slug: str, findings: list[StructuredFinding]) -> ResearchReport:
    return ResearchReport(
        topic="European PD",
        slug=slug,
        report_type="investor_brief",
        facts=[],
        citations=[],
        markdown="# PD",
        structured_findings=findings,
    )


def test_compare_reports_added_removed():
    prev = _report("prev", [
        StructuredFinding(entity="Ares", signal="Fund closed", date="2026-01", signal_type="fund_close"),
        StructuredFinding(entity="ICG", signal="Raising Europe fund", date="2026-02", signal_type="fundraise"),
    ])
    curr = _report("curr", [
        StructuredFinding(entity="ICG", signal="Raising Europe fund", date="2026-02", signal_type="fundraise"),
        StructuredFinding(entity="Blackstone", signal="New BDC launch", date="2026-03", signal_type="product_launch"),
    ])
    delta = compare_reports(prev, curr, watch_id="w1", run_id="r1")
    assert any(a.entity == "Blackstone" for a in delta.added)
    assert any(r.entity == "Ares" for r in delta.removed)
    assert delta.unchanged_count >= 1
    assert "Added" in delta.summary_markdown
    print("test_compare_reports_added_removed: PASS")


def test_compare_reports_first_run_all_added():
    curr = _report("curr", [
        StructuredFinding(entity="X", signal="Deal", date="2026-07", signal_type="deployment"),
    ])
    delta = compare_reports(None, curr, watch_id="w1", run_id="r0")
    assert len(delta.added) == 1
    assert delta.removed == []
    assert delta.prev_slug == ""
    print("test_compare_reports_first_run_all_added: PASS")


def test_compare_reports_fact_fallback():
    prev = ResearchReport(
        topic="t",
        slug="p",
        facts=[
            ExtractedFact(
                fact="European fundraising rebounded",
                source_url="https://a.com",
                source_title="A",
                quoted_text="rebounded",
                confidence="high",
                signal_type="fundraise",
            )
        ],
        citations=[],
        markdown="m",
    )
    curr = ResearchReport(
        topic="t",
        slug="c",
        facts=[
            ExtractedFact(
                fact="Defaults rose in mid-market",
                source_url="https://b.com",
                source_title="B",
                quoted_text="defaults rose",
                confidence="medium",
                signal_type="default_distress",
            )
        ],
        citations=[],
        markdown="m",
    )
    delta = compare_reports(prev, curr, watch_id="w", run_id="r")
    assert len(delta.added) >= 1
    assert len(delta.removed) >= 1
    print("test_compare_reports_fact_fallback: PASS")


if __name__ == "__main__":
    test_compare_reports_added_removed()
    test_compare_reports_first_run_all_added()
    test_compare_reports_fact_fallback()
    print("All watchlist delta tests passed!")
