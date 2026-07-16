"""Source catalog and router models (Step 39)."""
from pydantic import BaseModel, Field

from models import ExtractedFact, SearchResult


class SourceEntry(BaseModel):
    """One curated source in the catalog."""
    id: str
    name: str = ""
    domain: str
    language: str = "en"
    category: str = "media"
    tags: list[str] = Field(default_factory=list)
    trust_tier: str = Field(default="secondary", pattern="^(primary|secondary)$")
    access_modes: list[str] = Field(default_factory=lambda: ["site_search"])
    search_templates: list[str] = Field(default_factory=list)
    entry_urls: list[str] = Field(default_factory=list)
    notes: str = ""


class RouterDecision(BaseModel):
    """LLM-constrained source routing decision."""
    selected_source_ids: list[str] = Field(default_factory=list)
    direct_url_fetches: list[str] = Field(default_factory=list)
    site_queries: list[str] = Field(default_factory=list)
    rationale: str = ""
    defer_open_web: bool = False
    fallback: bool = False


class ResearchState(BaseModel):
    """Mutable state for the coverage-driven research loop."""
    topic: str
    max_sources: int = 10
    hop: int = 0
    router_calls: int = 0
    facts: list[ExtractedFact] = Field(default_factory=list)
    all_results: list[SearchResult] = Field(default_factory=list)
    seen_urls: list[str] = Field(default_factory=list)
    topics_searched: list[str] = Field(default_factory=list)
    coverage_hints: list[str] = Field(default_factory=list)
    pending_site_queries: list[str] = Field(default_factory=list)
    pending_open_queries: list[str] = Field(default_factory=list)
    last_missing_dimensions: list[str] = Field(default_factory=list)
    last_coverage_score: float = 0.0
    stagnant_hops: int = 0

    model_config = {"arbitrary_types_allowed": True}

    @property
    def seen_url_set(self) -> set[str]:
        return set(self.seen_urls)

    def add_seen_urls(self, urls: list[str]) -> None:
        for url in urls:
            if url and url not in self.seen_urls:
                self.seen_urls.append(url)

    def sources_fetched_count(self) -> int:
        return len(self.seen_url_set)
