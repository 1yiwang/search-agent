"""Deterministic query expansion: dimension × info_type × date (Step 43)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

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
    # General deep-search suffixes (non-PD)
    "ranking_data": ["ranking", "market share", "users MAU", "top platforms"],
    "landscape": ["landscape", "ecosystem", "key players"],
    "comp_matrix": ["competitors", "vs", "comparison"],
    "market_forecast": ["market size", "growth", "forecast"],
    "funding_rounds": ["funding", "valuation", "Series", "investment"],
}

DIMENSION_INFO_TYPES: dict[str, list[str]] = {
    "fundraising": ["trends", "facts_data"],
    "volume_deals": ["examples", "facts_data"],
    "returns_spreads": ["experts", "comparisons"],
    "credit_risk": ["challenges", "facts_data"],
    "product_evergreen": ["examples", "trends"],
    "relative_value": ["comparisons", "experts"],
    "_diversity": ["facts_data", "experts"],
    "_empty": ["landscape", "ranking_data", "market_forecast", "funding_rounds"],
    "overview": ["landscape", "trends"],
    "ranking": ["ranking_data", "comp_matrix"],
    "competitors": ["comp_matrix", "examples"],
    "market": ["market_forecast", "facts_data"],
    "funding": ["funding_rounds", "examples"],
}

# Dimensions that should never use vertical catalog site: queries
OPEN_ONLY_DIMENSIONS = frozenset({
    "_empty", "overview", "ranking", "competitors", "market", "funding", "_diversity",
})

# Geographic / time / ranking-source angles for general open-web expand
GENERAL_REGION_VARIANTS = ("Europe", "EU", "UK", "Germany")
GENERAL_RANKING_SOURCES = (
    "Sensor Tower", "data.ai", "Similarweb", "TechCrunch", "Sifted",
)

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
    if info_type in ("facts_data", "ranking_data", "market_forecast"):
        return f"{suffixes[0]} {dates['month_year']}"
    if info_type in ("landscape", "comp_matrix", "funding_rounds"):
        return f"{suffixes[0]} {dates['half_year']}"
    return suffixes[0]


_GOAL_STOPWORDS = frozenset({
    "a", "an", "and", "the", "of", "in", "for", "to", "or", "vs", "versus",
    "on", "at", "by", "with", "from",
})


def _goal_keywords(goal: str, max_words: int = 8) -> str:
    """Distinctive tokens from research_goal for open-web queries."""
    words = [
        w for w in goal.replace(",", " ").replace("/", " ").split()
        if w and w.lower() not in _GOAL_STOPWORDS
    ]
    return " ".join(words[:max_words])


def _build_open_query(
    topic: str,
    suffix: str,
    dates: dict[str, str],
    *,
    research_goal: str = "",
) -> str:
    """Open-web query: topic seed + research_goal keywords + info_type suffix."""
    short_topic = topic.strip()
    if len(short_topic) > 100:
        short_topic = short_topic[:100].rsplit(" ", 1)[0]
    topic_seed = " ".join(short_topic.split()[:6])
    goal_part = _goal_keywords(research_goal)

    seen: set[str] = set()
    parts: list[str] = []
    for token in f"{topic_seed} {goal_part}".split():
        key = token.lower()
        if key not in seen:
            seen.add(key)
            parts.append(token)
    core = " ".join(parts[:12])
    return f"{core} {suffix} {dates['yyyy_mm']}".strip()


_ENTITY_STOPWORDS = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "into", "over", "under",
    "european", "europe", "market", "platform", "platforms", "company", "companies",
    "report", "according", "said", "year", "years", "billion", "million", "percent",
    "ranking", "rankings", "video", "short", "series", "ai", "h1", "h2",
})


def extract_followup_entities(
    facts: list[Any],
    *,
    topic: str = "",
    max_entities: int = 3,
) -> list[str]:
    """Deterministic proper-noun / quoted-name harvest for next-hop open queries."""
    import re
    from collections import Counter

    topic_lower = topic.lower()
    counts: Counter[str] = Counter()

    for fact in facts:
        text = " ".join(
            filter(
                None,
                [
                    getattr(fact, "fact", "") or "",
                    getattr(fact, "quoted_text", "") or "",
                    getattr(fact, "source_title", "") or "",
                    getattr(fact, "entity", "") or "",
                ],
            )
        )
        for m in re.finditer(r'"([^"]{2,60})"', text):
            name = m.group(1).strip()
            if name.lower() not in topic_lower and len(name) > 2:
                counts[name] += 3
        # Capitalized multi-word names (e.g. "Runway ML", "Kling AI")
        for m in re.finditer(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\b", text):
            name = m.group(1).strip()
            tokens = name.split()
            if name.lower() in _ENTITY_STOPWORDS:
                continue
            if all(t.lower() in _ENTITY_STOPWORDS for t in tokens):
                continue
            if name.lower() in topic_lower:
                continue
            if len(name) < 3:
                continue
            counts[name] += 1

    ranked = [n for n, _ in counts.most_common(max_entities * 3)]
    out: list[str] = []
    seen_lower: set[str] = set()
    for name in ranked:
        key = name.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        out.append(name)
        if len(out) >= max_entities:
            break
    return out


def _general_angle_queries(
    topic: str,
    dates: dict[str, str],
    *,
    hop: int,
    research_goal: str = "",
) -> list[ExpandedQuery]:
    """Region / ranking-source / prior-year variants for general open-web depth."""
    region = GENERAL_REGION_VARIANTS[hop % len(GENERAL_REGION_VARIANTS)]
    source = GENERAL_RANKING_SOURCES[hop % len(GENERAL_RANKING_SOURCES)]
    prior_year = str(max(2000, int(dates["year"]) - 1))
    goal = research_goal or RESEARCH_GOAL_FALLBACK
    queries = [
        ExpandedQuery(
            query=_build_open_query(
                topic, f"{region} ranking", dates, research_goal=goal,
            ),
            research_goal=goal,
            channel="open",
            template_id="region_variant",
            dimension="ranking",
        ),
        ExpandedQuery(
            query=_build_open_query(
                topic, f"{source} ranking data", dates, research_goal=goal,
            ),
            research_goal=goal,
            channel="open",
            template_id="ranking_source",
            dimension="ranking",
        ),
        ExpandedQuery(
            query=_build_open_query(
                topic,
                f"market size {prior_year}",
                dates,
                research_goal=goal,
            ),
            research_goal=goal,
            channel="open",
            template_id="prior_year",
            dimension="market",
        ),
    ]
    return queries


# Lazy import avoidance for research goal default text
RESEARCH_GOAL_FALLBACK = "Primary sources rankings reports and recent coverage for the topic"


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
    hop: int = 0,
    facts: list[Any] | None = None,
) -> ExpandResult:
    """Expand coverage gaps into executable site + open queries.

    ``hop`` rotates which info_type is used for site vs open so multi-hop
    searches do not repeat the same suffix matrix.
    """
    if not gap_hints and not facts:
        return ExpandResult()

    cap = max_queries if max_queries is not None else config.query_expand_max_per_hop
    when = current_date or datetime.now(timezone.utc).date()
    dates = _date_tokens(when)
    hop_index = max(0, hop)
    open_only_topic = not candidates

    expanded: list[ExpandedQuery] = []
    used_domains: set[str] = set()
    seen_queries: set[str] = set()

    def _append(eq: ExpandedQuery) -> None:
        key = eq.query.lower().strip()
        if key in seen_queries:
            return
        seen_queries.add(key)
        expanded.append(eq)

    for hint in (gap_hints or [])[:4]:
        dim = hint.dimension
        info_types = DIMENSION_INFO_TYPES.get(dim, ["facts_data", "experts"])
        n = len(info_types)
        goal = hint.research_goal
        open_only = dim in OPEN_ONLY_DIMENSIONS or open_only_topic

        if not open_only:
            source = _pick_source_for_dimension(dim, candidates, used_domains)
            if source:
                used_domains.add(source.domain)
                info_type = info_types[hop_index % n]
                suffix = _suffix_for_info_type(info_type, dates)
                _append(ExpandedQuery(
                    query=_build_site_query(source, topic, suffix, dates),
                    research_goal=goal,
                    channel="site",
                    template_id=info_type,
                    dimension=dim,
                ))

        open_type = info_types[(hop_index + 1) % n]
        open_suffix = _suffix_for_info_type(open_type, dates)
        _append(ExpandedQuery(
            query=_build_open_query(
                topic, open_suffix, dates, research_goal=goal,
            ),
            research_goal=goal,
            channel="open",
            template_id=open_type,
            dimension=dim,
        ))
        # Extra open angles on empty / general dimensions
        if open_only and len(info_types) > 1:
            for offset in range(n):
                alt_type = info_types[(hop_index + offset) % n]
                if alt_type == open_type:
                    continue
                alt_suffix = _suffix_for_info_type(alt_type, dates)
                _append(ExpandedQuery(
                    query=_build_open_query(
                        topic, alt_suffix, dates, research_goal=goal,
                    ),
                    research_goal=goal,
                    channel="open",
                    template_id=alt_type,
                    dimension=dim,
                ))

    if open_only_topic:
        primary_goal = (
            gap_hints[0].research_goal if gap_hints else RESEARCH_GOAL_FALLBACK
        )
        for eq in _general_angle_queries(
            topic, dates, hop=hop_index, research_goal=primary_goal,
        ):
            _append(eq)

        for entity in extract_followup_entities(facts or [], topic=topic):
            _append(ExpandedQuery(
                query=_build_open_query(
                    f"{entity} {topic}",
                    f"Europe {dates['half_year']}",
                    dates,
                    research_goal=f"Follow-up on {entity}",
                ),
                research_goal=f"Follow-up coverage for {entity}",
                channel="open",
                template_id="entity_followup",
                dimension="competitors",
            ))

    capped = len(expanded) > cap
    return ExpandResult(queries=expanded[:cap], capped=capped)


def gap_hints_to_router_hints(gap_hints: list[GapHint]) -> list[str]:
    """String hints for the LLM router (goal + dimension + suggested queries)."""
    hints: list[str] = []
    for h in gap_hints:
        parts: list[str] = []
        if h.research_goal:
            parts.append(h.research_goal)
        if h.dimension and h.dimension != "_diversity":
            parts.append(f"dimension={h.dimension}")
        if h.suggested_queries:
            parts.append("try: " + "; ".join(h.suggested_queries[:2]))
        if parts:
            hints.append(" | ".join(parts))
    return hints


def preferred_source_ids_for_gaps(gap_hints: list[GapHint]) -> list[str]:
    """Catalog source ids preferred for missing dimensions (deterministic)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for h in gap_hints:
        for sid in DIMENSION_SOURCE_IDS.get(h.dimension, []):
            if sid not in seen:
                seen.add(sid)
                ordered.append(sid)
    return ordered


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


def _domain_from_site_query(query: str) -> str | None:
    import re

    m = re.search(r"site:([^\s]+)", query or "", re.I)
    if not m:
        return None
    return m.group(1).lower().removeprefix("www.").rstrip("/")


def alternate_site_queries(
    failed_query: str,
    topic: str,
    *,
    missing_dimensions: list[str] | None = None,
    max_alternates: int = 2,
) -> list[str]:
    """Build site: queries on other catalog domains after an empty site search."""
    from sources.catalog import load_catalog

    failed_domain = _domain_from_site_query(failed_query)
    dims = missing_dimensions or ["_diversity"]
    preferred_ids: list[str] = []
    seen_ids: set[str] = set()
    for dim in dims:
        for sid in DIMENSION_SOURCE_IDS.get(dim, []):
            if sid not in seen_ids:
                seen_ids.add(sid)
                preferred_ids.append(sid)

    by_id = {e.id: e for e in load_catalog()}
    used_domains = {failed_domain} if failed_domain else set()
    alts: list[str] = []
    for sid in preferred_ids:
        entry = by_id.get(sid)
        if not entry:
            continue
        domain = entry.domain.lower().removeprefix("www.")
        if domain in used_domains:
            continue
        used_domains.add(domain)
        if entry.search_templates:
            q = entry.search_templates[0].replace("{topic}", topic[:80])
        else:
            q = f"site:{entry.domain} {topic[:60]}"
        alts.append(q)
        if len(alts) >= max_alternates:
            break
    return alts


def alternate_source_entry_urls(
    failed_url: str,
    *,
    missing_dimensions: list[str] | None = None,
    max_alternates: int = 2,
) -> list[str]:
    """After same-domain entry_urls fail, try landing pages from other preferred sources."""
    from urllib.parse import urlparse
    from sources.catalog import load_catalog

    host = (urlparse(failed_url).hostname or "").lower().removeprefix("www.")
    dims = missing_dimensions or ["_diversity"]
    preferred_ids: list[str] = []
    seen_ids: set[str] = set()
    for dim in dims:
        for sid in DIMENSION_SOURCE_IDS.get(dim, []):
            if sid not in seen_ids:
                seen_ids.add(sid)
                preferred_ids.append(sid)

    by_id = {e.id: e for e in load_catalog()}
    alts: list[str] = []
    for sid in preferred_ids:
        entry = by_id.get(sid)
        if not entry or not entry.entry_urls:
            continue
        domain = entry.domain.lower().removeprefix("www.")
        if host and domain == host:
            continue
        for url in entry.entry_urls:
            if url != failed_url and url not in alts:
                alts.append(url)
                break
        if len(alts) >= max_alternates:
            break
    return alts


def _iter_catalog_by_domain(domain: str):
    from sources.catalog import load_catalog

    for entry in load_catalog():
        if entry.domain.lower() == domain:
            yield entry
