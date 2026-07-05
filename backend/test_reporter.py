"""Smoke test for report generation."""
from models import ExtractedFact
from reporter import generate_report, _slugify


def test_slugify():
    assert _slugify("Hello World") == "hello-world"
    assert _slugify("Python: FastAPI & LLMs!") == "python-fastapi-llms"
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
    assert report.slug == "python-web-frameworks"
    assert len(report.citations) == 2
    assert "[^1]" in report.markdown
    assert "[^2]" in report.markdown
    print("test_generate_report: PASS")
    print(f"\nGenerated Markdown preview:\n{report.markdown[:500]}...")


if __name__ == "__main__":
    test_slugify()
    test_generate_report()
    print("All reporter tests passed!")
