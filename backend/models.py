"""Pydantic data models for Search Agent."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Structured signal taxonomy for private markets intelligence (Phase 2)."""
    FUND_CLOSE = "fund_close"
    FUNDRAISE = "fundraise"
    DEPLOYMENT = "deployment"
    REFINANCE = "refinance"
    DEFAULT_DISTRESS = "default_distress"
    SPREAD_MARKET = "spread_market"
    REGULATORY = "regulatory"
    TEAM_MOVE = "team_move"
    PRODUCT_LAUNCH = "product_launch"
    OTHER = "other"


class EntityType(str, Enum):
    """Entity taxonomy for private markets intelligence (Phase 2)."""
    FUND = "fund"
    MANAGER_GP = "manager_gp"
    BORROWER = "borrower"
    INVESTOR_LP = "investor_lp"
    REGULATOR = "regulator"
    OTHER = "other"


class ResearchRequest(BaseModel):
    """Incoming research request from the frontend."""
    topic: str = Field(..., min_length=3, max_length=500, description="Research topic/question")
    max_sources: int = Field(default=10, ge=3, le=30, description="Maximum sources to fetch")


class ResearchDimension(BaseModel):
    """A single research dimension with targeted search queries."""
    title: str = Field(..., min_length=2, max_length=200)
    queries: list[str] = Field(..., min_length=1, max_length=5)
    priority: int = Field(default=1, ge=1, le=10)
    info_type: str = Field(
        default="facts",
        description="facts | cases | criticism | trends",
    )


class ResearchPlan(BaseModel):
    """Structured research plan produced by the planner."""
    topic: str
    title: str
    date: str
    initial_research_summary: str = ""
    dimensions: list[ResearchDimension] = Field(default_factory=list)
    max_sections: int = 5


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
    event_date: str = Field(
        default="",
        description="Event date if stated in source (YYYY, YYYY-MM, or YYYY-MM-DD)",
    )
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


class SourceSnapshot(BaseModel):
    """Fetched source text saved with the report for citation preview."""
    url: str
    title: str = ""
    content_kind: str = Field(
        default="html",
        pattern="^(html|document|empty)$",
        description="html page, office/pdf document, or empty/failed fetch",
    )
    text: str = ""


class ReportMetadata(BaseModel):
    """Execution metadata for the report."""
    execution_time_seconds: float
    source_count: int
    topics_searched: list[str]
    started_at: str
    completed_at: str


class StructuredFinding(BaseModel):
    """One row in the structured findings table (Phase 0)."""
    entity: str = Field(default="", description="Company, fund, or organization")
    signal: str = Field(default="", description="What happened or was discovered")
    date: str = Field(default="", description="Event date if known, else empty")
    confidence: str = Field(default="medium", pattern="^(high|medium|low)$")
    citation_index: int = Field(default=0, ge=0, description="[^n] citation index")
    signal_type: str = Field(default="", description="SignalType value when classified")
    entity_type: str = Field(default="", description="EntityType value when classified")


class ReportSynthesis(BaseModel):
    """LLM-generated report narrative (expression only, facts are fixed)."""
    executive_summary: str = ""
    structured_findings: list[StructuredFinding] = Field(default_factory=list)
    coverage: str = ""
    gaps: str = ""
    fund_activity: str = Field(default="", description="Investor brief: fund/product section")
    credit_risk_watch: str = Field(default="", description="Investor brief: credit risk section")


class ResearchReport(BaseModel):
    """Final research report."""
    topic: str
    slug: str
    report_type: str = Field(
        default="intelligence_brief",
        description="intelligence_brief | investor_brief",
    )
    facts: list[ExtractedFact] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    markdown: str = ""
    html_url: str = ""
    metadata: Optional[ReportMetadata] = None
    summary: str = ""
    structured_findings: list[StructuredFinding] = Field(default_factory=list)
    coverage: str = ""
    gaps: str = ""
    fund_activity: str = ""
    credit_risk_watch: str = ""
    source_snapshots: list[SourceSnapshot] = Field(default_factory=list)


class SSEEvent(BaseModel):
    """Server-sent event for streaming progress."""
    event: str
    data: dict = Field(default_factory=dict)
