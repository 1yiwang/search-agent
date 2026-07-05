"""Tests for report persistence."""
import tempfile
from pathlib import Path

from models import ExtractedFact, ResearchReport, ReportMetadata
from report_store import clear_cache, load_report, persist_report


def test_persist_and_load_survives_cache_clear():
    with tempfile.TemporaryDirectory() as tmp:
        from config import config

        original_dir = config.report_output_dir
        config.report_output_dir = tmp
        clear_cache()

        try:
            report = ResearchReport(
                topic="Test topic",
                slug="test-topic",
                facts=[
                    ExtractedFact(
                        fact="A fact",
                        source_url="https://example.com",
                        source_title="Example",
                        quoted_text="quoted",
                        confidence="high",
                    )
                ],
                citations=[],
                markdown="# Test",
                html_url="/research/test-topic/",
                metadata=ReportMetadata(
                    execution_time_seconds=1.0,
                    source_count=1,
                    topics_searched=["Test topic"],
                    started_at="2026-01-01T00:00:00+00:00",
                    completed_at="2026-01-01T00:00:01+00:00",
                ),
            )
            persist_report(report)
            clear_cache()

            loaded = load_report("test-topic")
            assert loaded is not None
            assert loaded.topic == "Test topic"
            assert loaded.html_url == "/research/test-topic/"
            assert len(loaded.facts) == 1
            assert Path(tmp, "test-topic", "data.json").is_file()
        finally:
            config.report_output_dir = original_dir
            clear_cache()


if __name__ == "__main__":
    test_persist_and_load_survives_cache_clear()
    print("test_report_store: PASS")
