"""JSONL event log for research SSE streams (Step 24)."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from config import config


class EventLog:
    """Buffers SSE events and flushes to reports/<slug>/events.jsonl."""

    def __init__(self, topic: str, mode: str = "quick"):
        self.run_id = str(uuid4())
        self.topic = topic
        self.mode = mode
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.seq = 0
        self._entries: list[dict] = []
        self._slug: str | None = None

    def record(self, event: str, data: dict) -> dict:
        """Append event to buffer; return SSE payload with seq + run_id."""
        self.seq += 1
        entry = {
            "seq": self.seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event": event,
            "data": data,
        }
        self._entries.append(entry)
        return {
            "event": event,
            "data": {
                **data,
                "seq": self.seq,
                "run_id": self.run_id,
            },
        }

    def bind_slug(self, slug: str) -> None:
        self._slug = slug

    def events_path(self, slug: str | None = None) -> Path:
        slug = slug or self._slug
        if not slug:
            raise ValueError("slug required")
        return Path(config.report_output_dir) / slug / "events.jsonl"

    def flush(self, slug: str | None = None) -> Path | None:
        """Write buffered events to disk."""
        slug = slug or self._slug
        if not slug or not self._entries:
            return None

        path = self.events_path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)

        meta = {
            "seq": 0,
            "ts": self.started_at,
            "run_id": self.run_id,
            "event": "session_meta",
            "data": {
                "topic": self.topic,
                "mode": self.mode,
                "slug": slug,
            },
        }

        with path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(meta, ensure_ascii=False) + "\n")
            for entry in self._entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return path


def load_events(slug: str) -> list[dict] | None:
    """Load events.jsonl for a report slug."""
    path = Path(config.report_output_dir) / slug / "events.jsonl"
    if not path.is_file():
        return None

    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events
