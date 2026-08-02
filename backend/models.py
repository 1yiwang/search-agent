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
    depth: str = Field(
        default="standard",
        description="Research depth tier: fast | standard | deep",
        pattern="^(fast|standard|deep)$",
    )
    brief_session_id: str | None = Field(
        default=None,
        description="Optional Wave 12a brief session; when set, loop binds to confirmed brief",
    )


class BriefDimension(BaseModel):
    """One research direction inside an industry ResearchBrief."""
    title: str = Field(..., min_length=2, max_length=200)
    research_goal: str = Field(default="", max_length=800)
    direction_detail: str = Field(
        default="",
        max_length=2500,
        description="Detailed retrieval brief: what to search, why, expected sources",
    )
    queries: list[str] = Field(default_factory=list, max_length=8)
    priority: int = Field(default=1, ge=1, le=10)
    info_type: str = Field(
        default="facts",
        description="facts | cases | criticism | trends",
    )
    phase_id: str = Field(default="", description="Optional framework phase id")
    direction_id: str = Field(
        default="",
        description="Stable id for budget/coverage (defaults to phase_id)",
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Named entities this direction must search for",
    )
    must_answer: list[str] = Field(
        default_factory=list,
        description="Concrete questions this direction must answer",
    )
    budget_weight: int = Field(default=1, ge=1, le=10)


class ResearchBrief(BaseModel):
    """Industry research brief — human-approved search overview (Wave 12a)."""
    topic: str
    problem_restatement: str = ""
    framework_id: str = "general_industry"
    clarify_answers: dict[str, str] = Field(default_factory=dict)
    phases: list[dict] = Field(
        default_factory=list,
        description="Ordered phases [{id, title, goal}]",
    )
    dimensions: list[BriefDimension] = Field(default_factory=list)
    deprioritize: list[str] = Field(default_factory=list)
    source_prefs: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    assumed_defaults: list[str] = Field(default_factory=list)
    overview_markdown: str = ""
    confirmed: bool = False


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
    signal_type: str = Field(
        default="other",
        description="SignalType value for private markets facts",
    )
    entity_type: str = Field(
        default="other",
        description="EntityType value when classified",
    )


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
    normalized_url: str = Field(
        default="",
        description="Normalized URL key for dedup and frontend snapshot lookup",
    )


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


class ReportArgument(BaseModel):
    """One supporting section under the report thesis (Wave 12b/12c)."""
    claim: str = Field(..., min_length=1, description="Single-sentence supporting claim")
    detail: str = Field(default="", description="Legacy short elaboration")
    body: str = Field(
        default="",
        description="Gemini-style section prose (~150–300 chars/words), may include [n] cites",
    )
    heading: str = Field(default="", description="Section heading from fixed outline")
    slot_id: str = Field(default="", description="Outline slot id")
    citation_indices: list[int] = Field(default_factory=list)
    confidence: str = Field(default="medium", pattern="^(high|medium|low)$")


class EvidenceDraftSlot(BaseModel):
    """One outline slot filled with fact indices (Pass A)."""
    slot_id: str
    title: str = ""
    writing_goal: str = ""
    fact_indices: list[int] = Field(default_factory=list)
    notes: str = ""
    required: bool = False


class EvidenceDraftQuarantine(BaseModel):
    fact_index: int
    reason: str = ""


class EvidenceDraft(BaseModel):
    """Intermediate draft after search — facts assigned to fixed slots (Wave 12c)."""
    topic_restatement: str = ""
    outline_id: str = "general_industry"
    slots: list[EvidenceDraftSlot] = Field(default_factory=list)
    quarantine: list[EvidenceDraftQuarantine] = Field(default_factory=list)
    sufficiency: str = Field(default="ok", pattern="^(thin|ok)$")


class ReportSynthesis(BaseModel):
    """LLM-generated report narrative (expression only, facts are fixed)."""
    thesis: str = Field(default="", description="Single-sentence conclusion")
    arguments: list[ReportArgument] = Field(default_factory=list)
    executive_summary: str = Field(
        default="",
        description="Compat: mirrors thesis (or legacy multi-sentence summary)",
    )
    structured_findings: list[StructuredFinding] = Field(default_factory=list)
    coverage: str = ""
    gaps: str = ""
    fund_activity: str = Field(default="", description="Investor brief: fund/product section")
    credit_risk_watch: str = Field(default="", description="Investor brief: credit risk section")
    outline_id: str = ""
    draft_sufficiency: str = ""


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
    thesis: str = ""
    arguments: list[ReportArgument] = Field(default_factory=list)
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
