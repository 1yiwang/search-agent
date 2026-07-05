"""Pydantic data models for Search Agent."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Incoming research request from the frontend."""
    topic: str = Field(..., min_length=3, max_length=500, description="Research topic/question")
    max_sources: int = Field(default=10, ge=3, le=30, description="Maximum sources to fetch")


class SearchResult(BaseModel):
    """A single search result from DuckDuckGo or other engines."""
    url: str
    title: str
    snippet: str
    full_text: str = ""  # populated after web_fetch


class ExtractedFact(BaseModel):
    """A single fact extracted from a source."""
    fact: str = Field(..., description="The fact statement")
    source_url: str
    source_title: str
    quoted_text: str = Field(..., description="The original text supporting this fact")
    confidence: str = Field(default="medium", pattern="^(high|medium|low)$")


class Citation(BaseModel):
    """Citation entry linking report text to source."""
    index: int = Field(..., description="Citation number, e.g. 1 for [¹]")
    source_name: str
    source_url: str
    quoted_text: str
    highlight_anchor: str = Field(
        default="",
        description="Substring to highlight in the source text",
    )


class ReportMetadata(BaseModel):
    """Execution metadata for the report."""
    execution_time_seconds: float
    source_count: int
    topics_searched: list[str]
    started_at: str
    completed_at: str


class ResearchReport(BaseModel):
    """Final research report."""
    topic: str
    slug: str
    facts: list[ExtractedFact] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    markdown: str = ""
    html_url: str = ""
    metadata: Optional[ReportMetadata] = None


class SSEEvent(BaseModel):
    """Server-sent event for streaming progress."""
    event: str
    data: dict = Field(default_factory=dict)
