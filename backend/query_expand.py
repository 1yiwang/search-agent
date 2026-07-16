"""Deterministic query expansion: dimension × info_type × date (Step 43)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from config import config
from coverage import GapHint
from sources.models import SourceEntry

INFO_TYPE_SUFFIXES: dict[str, list[str]] = {
    "facts_data": ["statistics", "data", "market size", "fundraising volume"],
    "examples": ["case study", "fund launch", "deal"],
    "experts": ["research", "outlook", "insights"],
    "trends": ["trends", "outlook"],
    "comparisons": ["vs leveraged loans", "vs high yield", "vs US"],
    "challenges": ["default", "distress", "risk", "criticism"],
}

DIMENSION_INFO_TYPES: dict[str, list[str]] = {
    "fundraising": ["trends", "facts_data"],
    "volume_deals": ["examples", "facts_data"],
    "returns_spreads": ["experts", "comparisons"],
    "credit_risk": ["challenges", "facts_data"],
    "product_evergreen": ["examples", "trends"],
    "relative_value": ["comparisons", "experts"],
    "_diversity": ["facts_data", "experts"],
}

DIMENSION_SOURCE_IDS: dict[str, list[str]] = {
    "fundraising": ["pei", "preqin_insights", "stepstone_insights"],
    "volume_deals": ["pei", "fnlondon", "levfin_insights"],
    "returns_spreads": ["stepstone_insights", "preqin_insights", "icg_news"],
    "credit_risk": ["pei", "altassets", "fnlondon"],
    "product_evergreen": ["stepstone_insights", "pei", "lux_flag"],
    "relative_value": ["stepstone_insights", "levfin_insights", "fnlondon"],
    "_diversity": ["pei", "preqin_insights", "stepstone_insights", "fnlondon"],
}


@dataclass
class ExpandedQuery:
    query: str
    research_goal: str
    channel: str  # "site" | "open"
    template_id: str
    dimension: str = ""


@dataclass
class ExpandResult:
    queries: list[ExpandedQuery] = field(default_factory=list)
    capped: bool = False


def _date_tokens(current: date) -> dict[str, str]:
    month = current.month
    year = current.year
    half = "H1" if month <= 6 else "H2"
    return {
        "yyyy_mm": f"{year}-{month:02d}",
        "half_year": f"{half} {year}",
        "month_year": current.strftime("%B %Y"),
        "year": str(year),
    }


def _pick_source_for_dimension(
    dimension: str,
    candidates: list[SourceEntry],
    used_domains: set[str],
) -> SourceEntry | None:
    candidate_ids = {c.id for c in candidates}
    for source_id in DIMENSION_SOURCE_IDS.get(dimension, []):
        if source_id not in candidate_ids:
            continue
        entry = next((c for c in candidates if c.id == source_id), None)
        if entry and entry.domain not in used_domains:
            return entry
    for entry in candidates:
        if entry.domain not in used_domains:
            return entry
    return candidates[0] if candidates else None


def _suffix_for_info_type(info_type: str, dates: dict[str, str]) -> str:
    suffixes = INFO_TYPE_SUFFIXES.get(info_type, ["research"])
    if info_type == "trends":
        return f"{suffixes[0]} {dates['half_year']} {suffixes[1]}"
    if info_type == "facts_data":
        return f"{suffixes[0]} {dates['month_year']}"
    return suffixes[0]


def _build_open_query(topic: str, suffix: str, dates: dict[str, str]) -> str:
    short_topic = topic.strip()
    if len(short_topic) > 120:
        short_topic = short_topic[:120].rsplit(" ", 1)[0]
    return f"{short_topic} {suffix} {dates['yyyy_mm']}"


def _build_site_query(
    entry: SourceEntry,
    topic: str,
    suffix: str,
    dates: dict[str, str],
) -> str:
    if entry.search_templates:
        template = entry.search_templates[0]
        base = template.replace("{topic}", topic[:80])
        return f"{base} {suffix} {dates['half_year']}"
    return f"site:{entry.domain} {topic[:60]} {suffix} {dates['month_year']}"


def expand_queries(
    topic: str,
    gap_hints: list[GapHint],
    candidates: list[SourceEntry],
    *,
    current_date: date | None = None,
    max_queries: int | None = None,
) -> ExpandResult:
    """Expand coverage gaps into executable site + open queries."""
    if not gap_hints:
        return ExpandResult()

    cap = max_queries if max_queries is not None else config.query_expand_max_per_hop
    when = current_date or datetime.now(timezone.utc).date()
    dates = _date_tokens(when)

    expanded: list[ExpandedQuery] = []
    used_domains: set[str] = set()

    for hint in gap_hints[:3]:
        dim = hint.dimension
        info_types = DIMENSION_INFO_TYPES.get(dim, ["facts_data", "experts"])
        goal = hint.research_goal

        source = _pick_source_for_dimension(dim, candidates, used_domains)
        if source:
            used_domains.add(source.domain)
            info_type = info_types[0]
            suffix = _suffix_for_info_type(info_type, dates)
            expanded.append(ExpandedQuery(
                query=_build_site_query(source, topic, suffix, dates),
                research_goal=goal,
                channel="site",
                template_id=info_type,
                dimension=dim,
            ))

        open_type = info_types[-1] if len(info_types) > 1 else info_types[0]
        open_suffix = _suffix_for_info_type(open_type, dates)
        expanded.append(ExpandedQuery(
            query=_build_open_query(topic, open_suffix, dates),
            research_goal=goal,
            channel="open",
            template_id=open_type,
            dimension=dim,
        ))

    capped = len(expanded) > cap
    return ExpandResult(queries=expanded[:cap], capped=capped)


def gap_hints_to_router_hints(gap_hints: list[GapHint]) -> list[str]:
    """Back-compat string hints for the LLM router."""
    return [h.research_goal for h in gap_hints]


def alternate_entry_urls(failed_url: str) -> list[str]:
    """Return other entry_urls from the same catalog source (fetch retry)."""
    from urllib.parse import urlparse

    host = (urlparse(failed_url).hostname or "").lower().removeprefix("www.")
    if not host:
        return []

    for entry in _iter_catalog_by_domain(host):
        alts = [u for u in entry.entry_urls if u != failed_url]
        if alts:
            return alts
    return []


def _iter_catalog_by_domain(domain: str):
    from sources.catalog import load_catalog

    for entry in load_catalog():
        if entry.domain.lower() == domain:
            yield entry
