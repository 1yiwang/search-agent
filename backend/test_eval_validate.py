"""Unit tests for eval validation (no live API calls)."""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "backend"))

from models import ExtractedFact, ReportMetadata, ResearchReport
from eval.validate import GoldenCase, validate_report


def _fact(
    text: str,
    url: str,
    *,
    signal_type: str = "other",
    quoted: str | None = None,
) -> ExtractedFact:
    return ExtractedFact(
        fact=text,
        source_url=url,
        source_title="T",
        quoted_text=quoted or text,
        confidence="high",
        signal_type=signal_type,
    )


def test_validate_passes_good_report():
    case = GoldenCase(
        id="test",
        topic="Python 3.12",
        min_sources=2,
        min_facts=2,
        required_keywords=["3.12"],
    )
    report = ResearchReport(
        topic="Python 3.12",
        slug="python-312",
        facts=[
            ExtractedFact(
                fact="Python 3.12 added new typing features",
                source_url="https://a.com",
                source_title="A",
                quoted_text="3.12 added new typing",
                confidence="high",
            ),
            ExtractedFact(
                fact="Release in October 2023",
                source_url="https://b.com",
                source_title="B",
                quoted_text="released October 2023",
                confidence="medium",
            ),
        ],
        citations=[],
        markdown="# Python 3.12\n\nFacts about 3.12.",
    )
    assert validate_report(report, case) == []


def test_validate_catches_missing_keyword():
    case = GoldenCase(id="x", topic="t", min_sources=1, min_facts=1, required_keywords=["missing"])
    report = ResearchReport(
        topic="t",
        slug="t",
        facts=[
            ExtractedFact(
                fact="something",
                source_url="https://a.com",
                source_title="A",
                quoted_text="quote",
                confidence="low",
            )
        ],
        citations=[],
        markdown="# Hi",
    )
    errors = validate_report(report, case)
    assert any("keyword" in e for e in errors)


def test_validate_coverage_score_and_dimensions():
    case = GoldenCase(
        id="pd",
        topic="European corporate direct lending fundraising H1 2026",
        min_sources=2,
        min_facts=2,
        min_coverage_score=0.33,
        min_covered_dimensions=2,
    )
    # fundraising + volume_deals via keywords / signal_type
    report = ResearchReport(
        topic=case.topic,
        slug="pd",
        report_type="investor_brief",
        facts=[
            _fact(
                "European fundraising rebounded in H1",
                "https://pei.com/a",
                signal_type="fundraise",
            ),
            _fact(
                "LBO refinance volume rose across Europe",
                "https://preqin.com/b",
                signal_type="refinance",
            ),
        ],
        citations=[],
        markdown="# PD\nEuropean fundraising and LBO volume.",
    )
    assert validate_report(report, case) == []


def test_validate_coverage_score_fails_when_thin():
    case = GoldenCase(
        id="pd-thin",
        topic="European corporate direct lending fundraising H1 2026",
        min_sources=1,
        min_facts=1,
        min_coverage_score=0.5,
        min_covered_dimensions=3,
    )
    report = ResearchReport(
        topic=case.topic,
        slug="pd-thin",
        report_type="investor_brief",
        facts=[
            _fact("Something vague about markets", "https://a.com/x"),
        ],
        citations=[],
        markdown="# Thin",
    )
    errors = validate_report(report, case)
    assert any("coverage_score" in e for e in errors)
    assert any("covered dimensions" in e for e in errors)


def test_validate_require_open_web_query():
    case = GoldenCase(
        id="open",
        topic="European direct lending",
        min_sources=1,
        min_facts=1,
        require_open_web_query=True,
    )
    site_only = ResearchReport(
        topic=case.topic,
        slug="site",
        facts=[_fact("European direct lending grew", "https://a.com")],
        citations=[],
        markdown="European direct lending",
        metadata=ReportMetadata(
            execution_time_seconds=1.0,
            source_count=1,
            topics_searched=["site:pei.com European direct lending"],
            started_at="t0",
            completed_at="t1",
        ),
    )
    assert any("open-web" in e for e in validate_report(site_only, case))

    with_open = site_only.model_copy(
        update={
            "metadata": ReportMetadata(
                execution_time_seconds=1.0,
                source_count=1,
                topics_searched=[
                    "site:pei.com European direct lending",
                    "European direct lending fundraising 2026",
                ],
                started_at="t0",
                completed_at="t1",
            )
        }
    )
    assert validate_report(with_open, case) == []


def test_load_golden_cases_yaml():
    import yaml

    path = _REPO / "eval" / "golden_cases.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert len(data["cases"]) >= 3
    pd = next(c for c in data["cases"] if c["id"] == "european-pd-smoke")
    assert pd.get("min_coverage_score", 0) > 0
    assert pd.get("min_covered_dimensions", 0) >= 2
    assert pd.get("require_open_web_query") is True


if __name__ == "__main__":
    test_validate_passes_good_report()
    test_validate_catches_missing_keyword()
    test_validate_coverage_score_and_dimensions()
    test_validate_coverage_score_fails_when_thin()
    test_validate_require_open_web_query()
    test_load_golden_cases_yaml()
    print("test_eval_validate: PASS")
