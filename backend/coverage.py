"""Coverage-driven gap evaluation for investor_brief topics (Step 40)."""

from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass
class CoverageResult:
    score: float
    missing_dimensions: list[str] = field(default_factory=list)
    covered_dimensions: list[str] = field(default_factory=list)
    suggested_router_hints: list[str] = field(default_factory=list)
    should_continue: bool = False


def _fact_corpus(facts: list[ExtractedFact]) -> str:
    parts = [f.fact for f in facts]
    parts.extend(f.quoted_text for f in facts)
    return " ".join(parts).lower()


def _dimension_covered(corpus: str, keywords: list[str]) -> bool:
    return any(kw in corpus for kw in keywords)


def evaluate_coverage(
    topic: str,
    facts: list[ExtractedFact],
    *,
    hop: int,
    max_hops: int,
    coverage_threshold: float,
    sources_budget_remaining: int,
    stagnant_hops: int,
) -> CoverageResult:
    """Rule-based coverage check for private debt investor briefs."""
    report_type = detect_report_type(topic)
    if report_type != "investor_brief" or not facts:
        return CoverageResult(
            score=1.0 if facts else 0.0,
            should_continue=False,
        )

    corpus = _fact_corpus(facts)
    covered: list[str] = []
    missing: list[str] = []

    hint_map = {
        "fundraising": "European vs US private debt fundraising trends",
        "volume_deals": "direct lending volume LBO refinancings dividend recaps",
        "returns_spreads": "direct lending yields spreads returns 2025",
        "credit_risk": "private debt defaults leverage credit risk",
        "product_evergreen": "ELTIF evergreen BDC private credit fund launch Europe",
        "relative_value": "direct lending premium vs leveraged loans high yield",
    }

    for dim, keywords in INVESTOR_BRIEF_DIMENSIONS.items():
        if _dimension_covered(corpus, keywords):
            covered.append(dim)
        else:
            missing.append(dim)

    score = len(covered) / len(INVESTOR_BRIEF_DIMENSIONS) if INVESTOR_BRIEF_DIMENSIONS else 1.0
    hints = [hint_map[m] for m in missing[:3]]

    should_continue = (
        score < coverage_threshold
        and hop < max_hops
        and sources_budget_remaining > 0
        and stagnant_hops < 2
        and bool(missing)
    )

    return CoverageResult(
        score=round(score, 3),
        missing_dimensions=missing,
        covered_dimensions=covered,
        suggested_router_hints=hints,
        should_continue=should_continue,
    )
