"""Tests for source snapshot building."""
from models import SearchResult
from source_snapshots import build_source_snapshots


def test_build_source_snapshots_dedupes_urls():
    results = [
        SearchResult(
            url="https://example.com/a.docx",
            title="Doc A",
            snippet="",
            full_text="Sevensense Robotics is a startup.",
        ),
        SearchResult(
            url="https://example.com/a.docx",
            title="Doc A duplicate",
            snippet="",
            full_text="ignored duplicate",
        ),
        SearchResult(
            url="https://example.com/page",
            title="Page",
            snippet="snippet only",
            full_text="",
        ),
    ]
    snaps = build_source_snapshots(results)
    assert len(snaps) == 2
    by_url = {s.url: s for s in snaps}
    assert by_url["https://example.com/a.docx"].content_kind == "document"
    assert "Sevensense" in by_url["https://example.com/a.docx"].text
    assert by_url["https://example.com/page"].content_kind == "html"
    print("test_build_source_snapshots_dedupes_urls: PASS")


if __name__ == "__main__":
    test_build_source_snapshots_dedupes_urls()
    print("All source_snapshots tests passed!")
