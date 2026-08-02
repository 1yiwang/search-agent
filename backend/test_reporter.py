"""Smoke test for report generation."""
from datetime import datetime, timezone

from models import ExtractedFact, ReportSynthesis, StructuredFinding
from reporter import generate_report, _slugify
from report_synthesis import detect_report_type


def test_slugify():
    now = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
    assert _slugify("Hello World", now) == "hello-world-20260706-120000"
    assert _slugify("Python: FastAPI & LLMs!", now) == "python-fastapi-llms-20260706-120000"
    print("test_slugify: PASS")


def test_generate_report():
    facts = [
        ExtractedFact(
            fact="Python was created in 1991",
            source_url="https://python.org/history",
            source_title="Python History",
            quoted_text="first released in 1991 by Guido van Rossum",
            confidence="high",
        ),
        ExtractedFact(
            fact="FastAPI is built on Starlette",
            source_url="https://fastapi.tiangolo.com",
            source_title="FastAPI Docs",
            quoted_text="FastAPI is a modern, fast web framework for building APIs with Python",
            confidence="high",
        ),
    ]
    report = generate_report("Python web frameworks", facts)
    assert report.slug.startswith("python-web-frameworks-")
    assert len(report.citations) == 2
    assert "[^1]" in report.markdown
    assert report.summary
    assert report.thesis or report.summary
    assert report.arguments is not None
    assert "## Conclusion" in report.markdown
    print("test_generate_report: PASS")


def test_investor_brief_report_type():
    topic = "European corporate direct lending fundraising trends 2026"
    assert detect_report_type(topic) == "investor_brief"
    facts = [
        ExtractedFact(
            fact="European fundraising rebounded in 2025.",
            source_url="https://www.stepstonegroup.com/news-insights/recent-trends-in-corporate-direct-lending-2h25/",
            source_title="StepStone 2H25",
            quoted_text="European fundraising rebounded after a weaker 2024",
            confidence="high",
        ),
    ]
    synthesis = ReportSynthesis(
        thesis="European PD fundraising improved in 2025.",
        executive_summary="European PD fundraising improved in 2025.",
        arguments=[],
        structured_findings=[
            StructuredFinding(
                entity="European PD market",
                signal="Fundraising rebound",
                date="2025",
                confidence="high",
                citation_index=1,
                signal_type="fundraise",
            ),
        ],
        fund_activity="Evergreen funds grew.",
        credit_risk_watch="Defaults remain below historical averages.",
        coverage="StepStone research",
        gaps="No LCD data",
    )
    report = generate_report(topic, facts, synthesis=synthesis, report_type="investor_brief")
    assert report.report_type == "investor_brief"
    assert "# Investor Brief:" in report.markdown
    assert "## Conclusion" in report.markdown
    assert "## Fund & product activity" in report.markdown
    assert report.fund_activity
    print("test_investor_brief_report_type: PASS")


if __name__ == "__main__":
    test_slugify()
    test_generate_report()
    test_investor_brief_report_type()
    print("All reporter tests passed!")
