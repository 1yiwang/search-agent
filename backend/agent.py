"""Search Agent orchestration: coordinates search -> extract -> dedup -> report."""
import asyncio
from datetime import datetime, timezone

from config import config
from models import ResearchDimension, ResearchPlan, ResearchRequest, ResearchReport
from search import search_and_fetch
from extraction import extract_facts
from dedup import deduplicate_facts, deduplicate_search_results
from reporter import generate_report


async def run_research(
    request: ResearchRequest,
    event_callback=None,
) -> ResearchReport:
    """Execute the complete research pipeline.

    Args:
        request: The research topic and parameters.
        event_callback: Optional async callback(event_type, data) for SSE streaming.

    Returns:
        ResearchReport with facts, citations, and markdown.
    """
    started_at = datetime.now(timezone.utc)

    async def emit(event_type: str, data: dict):
        if event_callback:
            await event_callback(event_type, data)

    await emit("search_start", {"topic": request.topic, "max_sources": request.max_sources})

    # Phase 1: Search
    raw_results = await search_and_fetch(
        request.topic,
        request.max_sources,
        event_callback=emit,
    )
    await emit("search_complete", {"results_found": len(raw_results)})

    # Dedup search results
    unique_results = deduplicate_search_results(raw_results)
    await emit("dedup_complete", {
        "before": len(raw_results),
        "after": len(unique_results),
        "removed": len(raw_results) - len(unique_results),
    })

    # Phase 2: Extract facts
    successful_fetches = [r for r in unique_results if r.full_text and not r.full_text.startswith("[Failed")]
    await emit("extraction_start", {"sources_with_content": len(successful_fetches)})

    facts = await extract_facts(request.topic, successful_fetches)
    await emit("extraction_complete", {"facts_extracted": len(facts)})

    # Phase 3: Dedup facts
    unique_facts = deduplicate_facts(facts)
    await emit("fact_dedup_complete", {
        "before": len(facts),
        "after": len(unique_facts),
    })

    # Phase 4: Generate report
    await emit("report_start", {"fact_count": len(unique_facts)})
    report = generate_report(request.topic, unique_facts, started_at)
    await emit("report_complete", {
        "slug": report.slug,
        "citation_count": len(report.citations),
    })

    return report


async def _research_dimension(
    dimension: ResearchDimension,
    sources_per_query: int,
    emit,
) -> tuple[ResearchDimension, list]:
    """Search all queries for one dimension in parallel."""
    await emit("dimension_start", {
        "title": dimension.title,
        "queries": dimension.queries,
        "info_type": dimension.info_type,
    })

    async def search_query(query: str):
        return await search_and_fetch(
            query,
            sources_per_query,
            event_callback=emit,
        )

    query_batches = await asyncio.gather(*[search_query(q) for q in dimension.queries])
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
        _research_dimension(dim, sources_per_query, emit)
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

    unique_facts = deduplicate_facts(facts)
    await emit("fact_dedup_complete", {
        "before": len(facts),
        "after": len(unique_facts),
    })

    await emit("report_start", {"fact_count": len(unique_facts)})
    report = generate_report(plan.title or plan.topic, unique_facts, started_at)
    if report.metadata:
        report.metadata.topics_searched = topics_searched
    await emit("report_complete", {
        "slug": report.slug,
        "citation_count": len(report.citations),
    })

    return report
