"""Unit tests for JSONL event log."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from event_log import EventLog, load_events


def test_event_log_record_and_flush():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("event_log.config") as mock_config:
            mock_config.report_output_dir = tmp
            log = EventLog("EU AI Act", mode="quick")
            log.record("search_start", {"topic": "EU AI Act"})
            log.record("search_complete", {"results_found": 5})
            path = log.flush("eu-ai-act")

        assert path is not None
        assert path.name == "events.jsonl"
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3  # meta + 2 events
        meta = json.loads(lines[0])
        assert meta["event"] == "session_meta"
        assert meta["data"]["mode"] == "quick"
        event = json.loads(lines[1])
        assert event["event"] == "search_start"
        assert event["seq"] == 1
        assert event["run_id"] == meta["run_id"]


def test_load_events():
    with tempfile.TemporaryDirectory() as tmp:
        slug_dir = Path(tmp) / "test-slug"
        slug_dir.mkdir()
        path = slug_dir / "events.jsonl"
        path.write_text('{"event":"session_meta","data":{}}\n', encoding="utf-8")

        with patch("event_log.config") as mock_config:
            mock_config.report_output_dir = tmp
            events = load_events("test-slug")

        assert events is not None
        assert len(events) == 1


if __name__ == "__main__":
    test_event_log_record_and_flush()
    test_load_events()
    print("test_event_log: PASS")
