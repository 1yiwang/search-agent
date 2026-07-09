"""Search Agent orchestration: coordinates search -> extract -> dedup -> report."""
import asyncio
from datetime import datetime, timezone

from config import config
from models import ResearchDimension, ResearchPlan, ResearchRequest, ResearchReport
from search import search_topic_with_seeds
from extraction import extract_facts
from dedup import deduplicate_search_results
from reporter import generate_report
from report_synthesis import detect_report_type, synthesize_report
from multihop import finalize_facts, urls_from_results
from research_loop import run_research_loop
from sources.seeds import augment_queries


async def run_research(
    request: ResearchRequest,
    event_callback=None,
) -> ResearchReport:
    """Execute the complete research pipeline via coverage-driven loop."""
    if config.router_enabled:
        return await run_research_loop(request, event_callback=event_callback)

    started_at = datetime.now(timezone.utc)

    async def emit(event_type: str, data: dict):
        if event_callback:
            await event_callback(event_type, data)

    await emit("search_start", {"topic": request.topic, "max_sources": request.max_sources})

    raw_results, seed_topics = await search_topic_with_seeds(
        request.topic,
        request.max_sources,
        event_callback=emit,
    )
    await emit("search_complete", {"results_found": len(raw_results)})

    unique_results = deduplicate_search_results(raw_results)
    await emit("dedup_complete", {
        "before": len(raw_results),
        "after": len(unique_results),
        "removed": len(raw_results) - len(unique_results),
    })

    successful_fetches = [r for r in unique_results if r.full_text and not r.full_text.startswith("[Failed")]
    await emit("extraction_start", {"sources_with_content": len(successful_fetches)})

    facts = await extract_facts(request.topic, successful_fetches)
    await emit("extraction_complete", {"facts_extracted": len(facts)})

    seen_urls = urls_from_results(unique_results)
    topics_searched = seed_topics
    sources_per_query = min(config.multihop_sources_per_query, request.max_sources)

    verified_facts, _ = await finalize_facts(
        request.topic,
        facts,
        seen_urls,
        topics_searched,
        sources_per_query,
        emit,
    )

    await emit("report_start", {"fact_count": len(verified_facts)})
    report_type = detect_report_type(request.topic)
    synthesis = await synthesize_report(
        request.topic, verified_facts, topics_searched, report_type=report_type,
    )
    report = generate_report(
        request.topic,
        verified_facts,
        started_at,
        synthesis=synthesis,
        topics_searched=topics_searched,
        fetched_results=unique_results,
        report_type=report_type,
    )
    await emit("report_complete", {
        "slug": report.slug,
        "citation_count": len(report.citations),
    })

    return report


async def _research_dimension(
    dimension: ResearchDimension,
    sources_per_query: int,
    emit,
    plan_topic: str,
) -> tuple[ResearchDimension, list]:
    """Search all queries for one dimension in parallel."""
    await emit("dimension_start", {
        "title": dimension.title,
        "queries": dimension.queries,
        "info_type": dimension.info_type,
    })

    queries = augment_queries(plan_topic, dimension.queries)

    async def search_query(query: str):
        results, _ = await search_topic_with_seeds(
            query,
            sources_per_query,
            event_callback=emit,
        )
        return results

    query_batches = await asyncio.gather(*[search_query(q) for q in queries])
    results = []
    for batch in query_batches:
        results.extend(batch)

    await emit("dimension_complete", {
        "title": dimension.title,
        "results_found": len(results),
    })
    return dimension, results


async def run_deep_research(
    plan: ResearchPlan,
    sources_per_query: int | None = None,
    event_callback=None,
) -> ResearchReport:
    """Execute deep research: parallel dimension searches, then extract and report."""
    if sources_per_query is None:
        sources_per_query = config.deep_sources_per_query

    started_at = datetime.now(timezone.utc)

    async def emit(event_type: str, data: dict):
        if event_callback:
            await event_callback(event_type, data)

    await emit("plan_start", {
        "topic": plan.topic,
        "title": plan.title,
        "dimension_count": len(plan.dimensions),
    })

    if not plan.dimensions:
        return await run_research(
            ResearchRequest(topic=plan.topic, max_sources=config.planner_initial_sources),
            event_callback=event_callback,
        )

    dimension_pairs = await asyncio.gather(*[
        _research_dimension(dim, sources_per_query, emit, plan.topic)
        for dim in plan.dimensions
    ])

    raw_results = []
    topics_searched: list[str] = []
    for dimension, results in dimension_pairs:
        raw_results.extend(results)
        topics_searched.extend(dimension.queries)

    await emit("search_complete", {"results_found": len(raw_results)})

    unique_results = deduplicate_search_results(raw_results)
    await emit("dedup_complete", {
        "before": len(raw_results),
        "after": len(unique_results),
        "removed": len(raw_results) - len(unique_results),
    })

    successful_fetches = [
        r for r in unique_results
        if r.full_text and not r.full_text.startswith("[Failed")
    ]
    await emit("extraction_start", {"sources_with_content": len(successful_fetches)})

    async def extract_dimension(dimension: ResearchDimension, results: list):
        dim_results = deduplicate_search_results(results)
        successful = [
            r for r in dim_results
            if r.full_text and not r.full_text.startswith("[Failed")
        ]
        topic = f"{plan.topic} — {dimension.title}"
        return await extract_facts(topic, successful)

    extract_batches = await asyncio.gather(*[
        extract_dimension(dim, results)
        for dim, results in dimension_pairs
    ])
    facts = []
    for batch in extract_batches:
        facts.extend(batch)

    await emit("extraction_complete", {"facts_extracted": len(facts)})

    seen_urls = urls_from_results(unique_results)
    verified_facts, _ = await finalize_facts(
        plan.topic,
        facts,
        seen_urls,
        topics_searched,
        sources_per_query,
        emit,
    )

    await emit("report_start", {"fact_count": len(verified_facts)})
    report_topic = plan.title or plan.topic
    report_type = detect_report_type(report_topic)
    synthesis = await synthesize_report(
        report_topic, verified_facts, topics_searched, report_type=report_type,
    )
    report = generate_report(
        report_topic,
        verified_facts,
        started_at,
        synthesis=synthesis,
        topics_searched=topics_searched,
        fetched_results=unique_results,
        report_type=report_type,
    )
    await emit("report_complete", {
        "slug": report.slug,
        "citation_count": len(report.citations),
    })

    return report
