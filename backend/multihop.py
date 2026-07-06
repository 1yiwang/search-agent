"""Multi-hop follow-up research from verifier gaps (Step 23)."""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from config import config
from dedup import deduplicate_facts, normalize_url
from extraction import extract_facts
from models import ExtractedFact, SearchResult
from search import search_topic_with_seeds
from verifier import VerificationStats, verify_and_review

EmitCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def urls_from_results(results: list[SearchResult]) -> set[str]:
    return {normalize_url(r.url) for r in results}


async def _fetch_follow_up_facts(
    topic: str,
    queries: list[str],
    sources_per_query: int,
    seen_urls: set[str],
    emit: EmitCallback,
) -> list[ExtractedFact]:
    """Search follow-up queries and extract facts from new URLs only."""

    async def search_one(query: str) -> list[SearchResult]:
        results, _ = await search_topic_with_seeds(
            query,
            sources_per_query,
            event_callback=emit,
        )
        return results

    batches = await asyncio.gather(*[search_one(q) for q in queries])
    new_results: list[SearchResult] = []
    for batch in batches:
        for result in batch:
            norm = normalize_url(result.url)
            if norm in seen_urls:
                continue
            seen_urls.add(norm)
            new_results.append(result)

    successful = [
        r for r in new_results
        if r.full_text and not r.full_text.startswith("[Failed")
    ]
    if not successful:
        return []

    return await extract_facts(topic, successful)


async def finalize_facts(
    topic: str,
    facts: list[ExtractedFact],
    seen_urls: set[str],
    topics_searched: list[str],
    sources_per_query: int | None,
    emit: EmitCallback,
) -> tuple[list[ExtractedFact], VerificationStats]:
    """Dedup, verify, then run up to MULTIHOP_MAX_HOPS follow-up search rounds."""
    if sources_per_query is None:
        sources_per_query = config.multihop_sources_per_query

    unique_facts = deduplicate_facts(facts)
    await emit("fact_dedup_complete", {
        "before": len(facts),
        "after": len(unique_facts),
    })

    await emit("verify_start", {"fact_count": len(unique_facts)})
    verified_facts, verify_stats = await verify_and_review(topic, unique_facts)
    await _emit_verify(emit, unique_facts, verified_facts, verify_stats)

    hop = 0
    while verify_stats.follow_up_queries and hop < config.multihop_max_hops:
        hop += 1
        queries = verify_stats.follow_up_queries[:2]
        topics_searched.extend(queries)

        await emit("multihop_start", {"hop": hop, "queries": queries})

        new_facts = await _fetch_follow_up_facts(
            topic,
            queries,
            sources_per_query,
            seen_urls,
            emit,
        )

        await emit("multihop_complete", {
            "hop": hop,
            "new_facts": len(new_facts),
            "queries": queries,
        })

        if not new_facts:
            break

        merged = deduplicate_facts(verified_facts + new_facts)
        verified_facts, verify_stats = await verify_and_review(topic, merged)
        await _emit_verify(emit, merged, verified_facts, verify_stats, hop=hop)

    return verified_facts, verify_stats


async def _emit_verify(
    emit: EmitCallback,
    before_facts: list[ExtractedFact],
    after_facts: list[ExtractedFact],
    stats: VerificationStats,
    hop: int | None = None,
) -> None:
    payload = {
        "before": len(before_facts),
        "after": len(after_facts),
        "corroborated": stats.corroborated,
        "boosted": stats.boosted,
        "demoted": stats.demoted,
        "removed_by_review": stats.removed_by_review,
        "follow_up_queries": stats.follow_up_queries,
    }
    if hop is not None:
        payload["hop"] = hop
    await emit("verify_complete", payload)
