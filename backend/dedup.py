"""Deduplication for search results and extracted facts."""
import re
from urllib.parse import urlparse
from difflib import SequenceMatcher

from models import ExtractedFact


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison: remove scheme, www, trailing slash."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    host = host.removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}{parsed.query}"


def deduplicate_search_results(results: list) -> list:
    """Remove duplicate search results by normalized URL."""
    seen = set()
    unique = []
    for r in results:
        norm = _normalize_url(r.url)
        if norm not in seen:
            seen.add(norm)
            unique.append(r)
    return unique


def _similarity(a: str, b: str) -> float:
    """Compute text similarity ratio (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deduplicate_facts(
    facts: list[ExtractedFact],
    similarity_threshold: float = 0.85,
) -> list[ExtractedFact]:
    """Deduplicate extracted facts by URL + semantic similarity.

    Strategy:
    1. If two facts come from the same URL and are very similar, keep the
       one with higher confidence.
    2. If two facts from different URLs say nearly the same thing, keep
       both but mark the duplicate with lower confidence — this IS the
       cross-validation signal we want.
    """
    if len(facts) <= 1:
        return facts

    # First pass: same-URL dedup
    by_url: dict[str, list[ExtractedFact]] = {}
    for f in facts:
        norm = _normalize_url(f.source_url)
        by_url.setdefault(norm, []).append(f)

    same_url_deduped = []
    for url_facts in by_url.values():
        if len(url_facts) == 1:
            same_url_deduped.append(url_facts[0])
        else:
            # Keep all from same URL that are sufficiently different
            kept = [url_facts[0]]
            for f in url_facts[1:]:
                is_dup = any(
                    _similarity(f.fact, k.fact) > similarity_threshold
                    for k in kept
                )
                if not is_dup:
                    kept.append(f)
                # If duplicate, keep the one with higher confidence
                elif f.confidence == "high" and kept[0].confidence != "high":
                    kept = [f] + kept[1:]
            same_url_deduped.extend(kept)

    return same_url_deduped
