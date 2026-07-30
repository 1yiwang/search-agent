"""Unit tests for watchlist store CRUD (Step 41a)."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from watchlist.models import WatchCreate, WatchUpdate
from watchlist.store import (
    create_watch,
    delete_watch,
    get_watch,
    list_watches,
    update_watch,
)


def test_watchlist_crud_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("watchlist.store.config") as mock_cfg:
            mock_cfg.watchlist_dir = str(Path(tmp) / "watchlists")
            created = create_watch(WatchCreate(
                topic="European direct lending weekly",
                max_sources=8,
                cadence="weekly",
                recency_days=14,
            ))
            assert created.id
            assert created.topic.startswith("European")
            assert get_watch(created.id) is not None
            assert len(list_watches()) == 1

            updated = update_watch(created.id, WatchUpdate(enabled=False, max_sources=12))
            assert updated is not None
            assert updated.enabled is False
            assert updated.max_sources == 12

            assert delete_watch(created.id) is True
            assert get_watch(created.id) is None
            assert list_watches() == []
    print("test_watchlist_crud_roundtrip: PASS")


if __name__ == "__main__":
    test_watchlist_crud_roundtrip()
    print("All watchlist store tests passed!")
