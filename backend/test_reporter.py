"""Smoke test for report generation."""
from datetime import datetime, timezone

from models import ExtractedFact
from reporter import generate_report, _slugify


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
    assert report.structured_findings
    assert "## Executive Summary" in report.markdown
    print("test_generate_report: PASS")


if __name__ == "__main__":
    test_slugify()
    test_generate_report()
    print("All reporter tests passed!")
