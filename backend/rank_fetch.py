"""Rank search snippets then fetch only top-K (Wave 10 Step 59)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from models import SearchResult

# Light authority boost for regulators / major media / research hosts
_AUTHORITY_SUFFIXES: tuple[tuple[str, float], ...] = (
    (".gov", 3.0),
    (".gov.cn", 2.5),
    (".admin.ch", 4.0),
    (".europa.eu", 3.5),
    (".edu", 2.0),
    ("bakom.admin.ch", 5.0),
    ("swisscom.ch", 3.0),
    ("sunrise.ch", 2.5),
    ("salt.ch", 2.5),
    ("reuters.com", 2.5),
    ("ft.com", 2.5),
    ("bloomberg.com", 2.5),
    ("techcrunch.com", 2.0),
    ("sifted.eu", 2.0),
    ("mckinsey.com", 3.0),
)


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _authority_score(url: str) -> float:
    host = _domain(url)
    score = 0.0
    for suffix, boost in _AUTHORITY_SUFFIXES:
        if host.endswith(suffix.lstrip(".")) or suffix in host:
            score = max(score, boost)
    if host.endswith(".ch"):
        score = max(score, 1.5)
    return score


def _token_overlap(topic: str, text: str) -> float:
    topic_tokens = {
        t.lower()
        for t in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", topic)
    }
    if not topic_tokens:
        return 0.0
    blob = (text or "").lower()
    hits = sum(1 for t in topic_tokens if t in blob)
    return hits / max(len(topic_tokens), 1)


def score_search_result(topic: str, result: SearchResult) -> float:
    """Higher = more worth fetching full text."""
    text = f"{result.title} {result.snippet}"
    overlap = _token_overlap(topic, text)
    authority = _authority_score(result.url)
    length_bonus = min(1.0, len(result.snippet or "") / 200.0)
    return overlap * 5.0 + authority + length_bonus


def rank_search_results(topic: str, results: list[SearchResult]) -> list[SearchResult]:
    return sorted(
        results,
        key=lambda r: score_search_result(topic, r),
        reverse=True,
    )


def select_top_k_for_fetch(
    topic: str,
    results: list[SearchResult],
    *,
    k: int,
) -> list[SearchResult]:
    if k <= 0:
        return []
    ranked = rank_search_results(topic, results)
    return ranked[:k]
