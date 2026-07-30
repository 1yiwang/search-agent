"""Watchlist and delta models (Phase 3 / Step 41)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class WatchItem(BaseModel):
    id: str
    topic: str = Field(..., min_length=3, max_length=500)
    max_sources: int = Field(default=10, ge=3, le=30)
    cadence: Literal["manual", "weekly"] = "manual"
    enabled: bool = True
    baseline_slug: str = ""
    latest_slug: str = ""
    last_run_at: str = ""
    created_at: str = ""
    recency_days: int = Field(default=14, ge=1, le=365)
    latest_delta_id: str = ""


class WatchCreate(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    max_sources: int = Field(default=10, ge=3, le=30)
    cadence: Literal["manual", "weekly"] = "manual"
    recency_days: int = Field(default=14, ge=1, le=365)
    baseline_slug: str = ""


class WatchUpdate(BaseModel):
    topic: Optional[str] = Field(default=None, min_length=3, max_length=500)
    max_sources: Optional[int] = Field(default=None, ge=3, le=30)
    cadence: Optional[Literal["manual", "weekly"]] = None
    enabled: Optional[bool] = None
    recency_days: Optional[int] = Field(default=None, ge=1, le=365)


class DeltaFinding(BaseModel):
    """One finding row in a watch delta."""
    key: str = ""
    entity: str = ""
    signal: str = ""
    signal_type: str = ""
    date: str = ""
    confidence: str = ""
    citation_index: int = 0
    fact: str = ""
    source_url: str = ""
    change_note: str = ""


class WatchDelta(BaseModel):
    watch_id: str
    run_id: str
    prev_slug: str = ""
    curr_slug: str = ""
    created_at: str = ""
    added: list[DeltaFinding] = Field(default_factory=list)
    removed: list[DeltaFinding] = Field(default_factory=list)
    changed: list[DeltaFinding] = Field(default_factory=list)
    unchanged_count: int = 0
    summary_markdown: str = ""
