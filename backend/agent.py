"""Search Agent orchestration: coordinates search -> extract -> dedup -> report."""
import asyncio
from datetime import datetime, timezone

from models import ResearchRequest, ResearchReport
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
    raw_results = await search_and_fetch(request.topic, request.max_sources)
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
