"""Coverage-driven gap evaluation (investor_brief + general topics)."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from config import config
from models import ExtractedFact
from report_synthesis import detect_report_type

INVESTOR_BRIEF_DIMENSIONS: dict[str, list[str]] = {
    "fundraising": [
        "fundraising", "fundraise", "capital raised", "募资", "rebounded", "rebound",
        "europe", "european", "weak", "healthy",
    ],
    "volume_deals": [
        "volume", "lbo", "m&a", "refinanc", "dividend recap", "deal", "transaction",
        "交易量", "refinance",
    ],
    "returns_spreads": [
        "yield", "spread", "return", "9%", "10%", "gross", "base rate", "利差", "收益",
    ],
    "credit_risk": [
        "default", "leverage", "ltv", "coverage ratio", "distress", "违约", "credit risk",
        "borrower",
    ],
    "product_evergreen": [
        "eltif", "evergreen", "bdc", "scred", "crdex", "product", "launch", "umbrella",
        "private wealth", "eltif",
    ],
    "relative_value": [
        "leveraged loan", "high yield", "public credit", "premium", "relative value",
        "public", "loan",
    ],
}

# Map extraction signal_type → coverage dimensions (AND with keyword match)
SIGNAL_TYPE_DIMENSIONS: dict[str, list[str]] = {
    "fundraise": ["fundraising"],
    "fund_close": ["fundraising", "product_evergreen"],
    "deployment": ["volume_deals"],
    "refinance": ["volume_deals"],
    "default_distress": ["credit_risk"],
    "spread_market": ["returns_spreads", "relative_value"],
    "regulatory": ["product_evergreen"],
    "product_launch": ["product_evergreen"],
    "team_move": [],
    "other": [],
}

# Deprecated alias — prefer config.min_unique_domains_target (Step 47).
MIN_UNIQUE_DOMAINS = config.min_unique_domains_target

RESEARCH_GOALS: dict[str, str] = {
    "fundraising": "European vs US private debt fundraising trends",
    "volume_deals": "direct lending volume LBO refinancings dividend recaps",
    "returns_spreads": "direct lending yields spreads returns 2025",
    "credit_risk": "private debt defaults leverage credit risk",
    "product_evergreen": "ELTIF evergreen BDC private credit fund launch Europe",
    "relative_value": "direct lending premium vs leveraged loans high yield",
    "_diversity": "Broaden sources across multiple independent publishers",
    # General deep-search gaps (non–private-debt topics)
    "_empty": "Primary sources rankings reports and recent coverage for the topic",
    "overview": "Market overview landscape key players Europe",
    "ranking": "Rankings market share users downloads MAU revenue",
    "competitors": "Competitor comparison platforms products feature matrix",
    "market": "Market size growth forecasts Europe 2025 2026",
    "funding": "Funding fundraising valuation investment rounds",
    "examples": "Case studies real-world deployments implementations examples",
    "challenges": "Challenges limitations risks criticisms barriers regulation",
    "experts": "Expert analysis analyst commentary industry research opinions",
}

GENERAL_MIN_FACTS = 8
GENERAL_MIN_DOMAINS = 5
GENERAL_GAP_ORDER = ("overview", "ranking", "competitors", "market", "funding")
GENERAL_SYNTHESIS_GATES: dict[str, list[str]] = {
    "examples": [
        "case study", "case studies", "example", "examples", "implementation",
        "deployed", "pilot", "客户", "案例", "落地",
    ],
    "challenges": [
        "challenge", "challenges", "limitation", "limitations", "risk", "risks",
        "criticism", "barrier", "regulatory", "privacy", "挑战", "风险", "限制", "监管",
    ],
    "experts": [
        "expert", "analyst", "according to", "research firm", "interview",
        "commentary", "专家", "分析师", "认为",
    ],
}


@dataclass
class GapHint:
    dimension: str
    research_goal: str
    suggested_queries: list[str] = field(default_factory=list)


@dataclass
class CoverageResult:
    score: float
    missing_dimensions: list[str] = field(default_factory=list)
    covered_dimensions: list[str] = field(default_factory=list)
    suggested_router_hints: list[str] = field(default_factory=list)
    gap_hints: list[GapHint] = field(default_factory=list)
    should_continue: bool = False
    unique_domains: int = 0
    source_diversity_ok: bool = True


def _fact_corpus(facts: list[ExtractedFact]) -> str:
    parts = [f.fact for f in facts]
    parts.extend(f.quoted_text for f in facts)
    return " ".join(parts).lower()


def _dimension_covered(corpus: str, keywords: list[str]) -> bool:
    return any(kw in corpus for kw in keywords)


def _dimensions_from_signal_types(facts: list[ExtractedFact]) -> set[str]:
    covered: set[str] = set()
    for fact in facts:
        st = (getattr(fact, "signal_type", "") or "").lower()
        for dim in SIGNAL_TYPE_DIMENSIONS.get(st, []):
            covered.add(dim)
    return covered


def _unique_domains_from_facts(facts: list[ExtractedFact]) -> int:
    domains: set[str] = set()
    for fact in facts:
        host = (urlparse(fact.source_url).hostname or "").lower().removeprefix("www.")
        if host:
            domains.add(host)
    return len(domains)


def _can_continue(
    *,
    hop: int,
    max_hops: int,
    sources_budget_remaining: int,
    stagnant_hops: int,
) -> bool:
    return (
        hop < max_hops
        and sources_budget_remaining > 0
        and stagnant_hops < 2
    )


def _evaluate_general_coverage(
    facts: list[ExtractedFact],
    *,
    hop: int,
    max_hops: int,
    sources_budget_remaining: int,
    stagnant_hops: int,
    domain_target: int,
) -> CoverageResult:
    """Open-web deep search coverage: fact count + source diversity."""
    target_domains = max(domain_target, GENERAL_MIN_DOMAINS)
    unique_domains = _unique_domains_from_facts(facts)
    source_diversity_ok = unique_domains >= target_domains
    fact_count = len(facts)
    can = _can_continue(
        hop=hop,
        max_hops=max_hops,
        sources_budget_remaining=sources_budget_remaining,
        stagnant_hops=stagnant_hops,
    )

    if not facts:
        # Multi-angle first hop: empty + ranking + overview + market (+ funding via expand)
        gap_hints = [
            GapHint(dimension="_empty", research_goal=RESEARCH_GOALS["_empty"]),
            GapHint(dimension="ranking", research_goal=RESEARCH_GOALS["ranking"]),
            GapHint(dimension="overview", research_goal=RESEARCH_GOALS["overview"]),
            GapHint(dimension="market", research_goal=RESEARCH_GOALS["market"]),
        ]
        return CoverageResult(
            score=0.0,
            missing_dimensions=["_empty", "ranking", "overview", "market"],
            covered_dimensions=[],
            suggested_router_hints=[h.research_goal for h in gap_hints],
            gap_hints=gap_hints,
            should_continue=can,
            unique_domains=unique_domains,
            source_diversity_ok=False,
        )

    score = min(1.0, fact_count / float(max(GENERAL_MIN_FACTS * 2, 16)))
    missing: list[str] = []
    gap_hints: list[GapHint] = []
    covered = ["facts"] if fact_count else []

    if fact_count < GENERAL_MIN_FACTS:
        missing.extend(list(GENERAL_GAP_ORDER))
        gap_hints.extend([
            GapHint(dimension=dim, research_goal=RESEARCH_GOALS[dim])
            for dim in GENERAL_GAP_ORDER
        ])
    if not source_diversity_ok:
        if "_diversity" not in missing:
            missing.insert(0, "_diversity")
        gap_hints.insert(0, GapHint(
            dimension="_diversity",
            research_goal=RESEARCH_GOALS["_diversity"],
        ))

    # Synthesis gates (DeerFlow Phase 3/4 → hard gaps): examples / challenges / experts
    corpus = _fact_corpus(facts)
    for gate, keywords in GENERAL_SYNTHESIS_GATES.items():
        if _dimension_covered(corpus, keywords):
            if gate not in covered:
                covered.append(gate)
        else:
            if gate not in missing:
                missing.append(gate)
            gap_hints.append(GapHint(
                dimension=gate,
                research_goal=RESEARCH_GOALS[gate],
            ))

    content_ok = fact_count >= GENERAL_MIN_FACTS
    gates_ok = all(
        _dimension_covered(corpus, kws) for kws in GENERAL_SYNTHESIS_GATES.values()
    )
    should_continue = can and (
        not content_ok or not source_diversity_ok or not gates_ok
    )

    return CoverageResult(
        score=round(score, 3),
        missing_dimensions=missing,
        covered_dimensions=covered,
        suggested_router_hints=[h.research_goal for h in gap_hints],
        gap_hints=gap_hints,
        should_continue=should_continue,
        unique_domains=unique_domains,
        source_diversity_ok=source_diversity_ok,
    )


def evaluate_coverage(
    topic: str,
    facts: list[ExtractedFact],
    *,
    hop: int,
    max_hops: int,
    coverage_threshold: float,
    sources_budget_remaining: int,
    stagnant_hops: int,
    min_unique_domains: int | None = None,
) -> CoverageResult:
    """Rule-based coverage: investor_brief dimensions or general deep-search."""
    report_type = detect_report_type(topic)
    unique_domains = _unique_domains_from_facts(facts)
    domain_target = (
        config.min_unique_domains_target
        if min_unique_domains is None
        else min_unique_domains
    )
    source_diversity_ok = unique_domains >= domain_target

    if report_type != "investor_brief":
        return _evaluate_general_coverage(
            facts,
            hop=hop,
            max_hops=max_hops,
            sources_budget_remaining=sources_budget_remaining,
            stagnant_hops=stagnant_hops,
            domain_target=domain_target,
        )

    if not facts:
        missing = list(INVESTOR_BRIEF_DIMENSIONS.keys())[:3]
        gap_hints = [
            GapHint(dimension=m, research_goal=RESEARCH_GOALS[m])
            for m in missing
        ]
        gap_hints.insert(0, GapHint(
            dimension="_empty",
            research_goal=RESEARCH_GOALS["_empty"],
        ))
        return CoverageResult(
            score=0.0,
            missing_dimensions=["_empty"] + missing,
            gap_hints=gap_hints,
            suggested_router_hints=[h.research_goal for h in gap_hints],
            should_continue=_can_continue(
                hop=hop,
                max_hops=max_hops,
                sources_budget_remaining=sources_budget_remaining,
                stagnant_hops=stagnant_hops,
            ),
            unique_domains=unique_domains,
            source_diversity_ok=source_diversity_ok,
        )

    corpus = _fact_corpus(facts)
    signal_dims = _dimensions_from_signal_types(facts)
    covered: list[str] = []
    missing: list[str] = []

    for dim, keywords in INVESTOR_BRIEF_DIMENSIONS.items():
        if _dimension_covered(corpus, keywords) or dim in signal_dims:
            covered.append(dim)
        else:
            missing.append(dim)

    score = len(covered) / len(INVESTOR_BRIEF_DIMENSIONS) if INVESTOR_BRIEF_DIMENSIONS else 1.0

    gap_hints: list[GapHint] = [
        GapHint(dimension=m, research_goal=RESEARCH_GOALS[m])
        for m in missing[:3]
    ]
    if not source_diversity_ok:
        gap_hints.insert(0, GapHint(
            dimension="_diversity",
            research_goal=RESEARCH_GOALS["_diversity"],
        ))
    hints = [h.research_goal for h in gap_hints]

    content_satisfied = score >= coverage_threshold
    should_continue = (
        (not content_satisfied or not source_diversity_ok)
        and _can_continue(
            hop=hop,
            max_hops=max_hops,
            sources_budget_remaining=sources_budget_remaining,
            stagnant_hops=stagnant_hops,
        )
        and (bool(missing) or not source_diversity_ok)
    )

    return CoverageResult(
        score=round(score, 3),
        missing_dimensions=missing,
        covered_dimensions=covered,
        suggested_router_hints=hints,
        gap_hints=gap_hints,
        should_continue=should_continue,
        unique_domains=unique_domains,
        source_diversity_ok=source_diversity_ok,
    )
