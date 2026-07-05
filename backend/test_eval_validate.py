"""Unit tests for eval validation (no live API calls)."""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "backend"))

from models import ExtractedFact, ResearchReport
from eval.validate import GoldenCase, validate_report


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


def test_load_golden_cases_yaml():
    import yaml

    path = _REPO / "eval" / "golden_cases.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert len(data["cases"]) >= 3


if __name__ == "__main__":
    test_validate_passes_good_report()
    test_validate_catches_missing_keyword()
    test_load_golden_cases_yaml()
    print("test_eval_validate: PASS")
