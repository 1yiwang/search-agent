"""Coverage-driven research loop with Source Router (Step 40)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from config import config
from coverage import evaluate_coverage
from dedup import deduplicate_facts, deduplicate_search_results, normalize_url
from extraction import extract_facts
from models import ExtractedFact, ResearchRequest, ResearchReport
from multilang import initial_open_queries
from query_expand import (
    expand_queries,
    gap_hints_to_router_hints,
    preferred_source_ids_for_gaps,
)
from reporter import generate_report
from report_synthesis import detect_report_type, synthesize_report
from sources.catalog import filter_candidates, intent_labels
from sources.executor import execute_router_decision
from sources.models import ResearchState
from sources.router import route_sources
from verifier import verify_and_review

EmitCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _verify_facts(
    topic: str,
    facts: list[ExtractedFact],
    emit: EmitCallback,
) -> list[ExtractedFact]:
    unique = deduplicate_facts(facts)
    await emit("fact_dedup_complete", {
        "before": len(facts),
        "after": len(unique),
    })
    await emit("verify_start", {"fact_count": len(unique)})
    verified, stats = await verify_and_review(topic, unique)
    await emit("verify_complete", {
        "before": len(unique),
        "after": len(verified),
        "corroborated": stats.corroborated,
        "boosted": stats.boosted,
        "demoted": stats.demoted,
        "removed_by_review": stats.removed_by_review,
        "follow_up_queries": stats.follow_up_queries,
        "hop": None,
    })
    return verified


async def run_research_loop(
    request: ResearchRequest,
    event_callback: EmitCallback | None = None,
) -> ResearchReport:
    """Execute coverage-driven search → extract → verify → report."""
    started_at = datetime.now(timezone.utc)

    async def emit(event_type: str, data: dict) -> None:
        if event_callback:
            await event_callback(event_type, data)

    state = ResearchState(
        topic=request.topic,
        max_sources=request.max_sources,
        topics_searched=[request.topic],
    )
    seen_urls: set[str] = set()

    await emit("search_start", {
        "topic": request.topic,
        "max_sources": request.max_sources,
        "router_enabled": config.router_enabled,
    })

    candidates = filter_candidates(request.topic)
    await emit("catalog_filtered", {
        "candidate_count": len(candidates),
        "intent": intent_labels(request.topic),
    })

    prev_fact_count = 0
    while True:
        budget_remaining = request.max_sources - state.sources_fetched_count()
        if budget_remaining <= 0:
            break
        if state.router_calls >= config.research_max_router_calls:
            break
        if state.hop > 0 and state.hop >= config.research_max_hops:
            break

        state.router_calls += 1
        decision = await route_sources(
            request.topic,
            coverage_hints=state.coverage_hints,
            candidates=candidates,
        )

        intents = intent_labels(request.topic)
        is_general = not candidates
        if is_general:
            # Open-web first: do not burn budget on irrelevant vertical site: queries.
            decision.site_queries = []
            decision.direct_url_fetches = []
            decision.defer_open_web = False
            decision.rationale = (
                (decision.rationale + " | " if decision.rationale else "")
                + "Open-web first (no vertical catalog match)"
            )

        if state.pending_site_queries and not is_general:
            merged = (state.pending_site_queries + decision.site_queries)[
                : config.router_max_site_queries
            ]
            decision.site_queries = merged
            state.pending_site_queries = []
        elif state.pending_site_queries and is_general:
            # General expands are open-only; drop pending site queries.
            state.pending_site_queries = []

        if state.pending_preferred_source_ids and not is_general:
            preferred = [
                sid for sid in state.pending_preferred_source_ids
                if sid in {c.id for c in candidates}
            ]
            if preferred:
                merged_ids = preferred + [
                    sid for sid in decision.selected_source_ids if sid not in preferred
                ]
                decision.selected_source_ids = merged_ids[
                    : config.router_max_sources_per_round
                ]
            state.pending_preferred_source_ids = []
        else:
            state.pending_preferred_source_ids = []

        await emit("source_router_decision", {
            "hop": state.hop,
            "selected_source_ids": decision.selected_source_ids,
            "site_queries": decision.site_queries,
            "direct_url_fetches": decision.direct_url_fetches,
            "rationale": decision.rationale,
            "defer_open_web": decision.defer_open_web,
            "fallback": decision.fallback,
            "open_web_first": is_general,
        })

        force_open = (
            is_general
            or (state.hop == 0 and not decision.defer_open_web)
            or bool(state.pending_open_queries)
            or (not state.facts and state.hop > 0)
        )
        new_results, searched = await execute_router_decision(
            request.topic,
            decision,
            seen_urls,
            budget_remaining=budget_remaining,
            event_callback=emit,
            force_open_web=force_open,
            open_queries=state.pending_open_queries or (
                initial_open_queries(request.topic, hop=state.hop)
                if is_general
                else None
            ),
            missing_dimensions=state.last_missing_dimensions or None,
            gap_hop=state.hop > 0 and (
                bool(state.last_missing_dimensions) or not state.facts
            ),
        )
        state.pending_open_queries = []
        for q in searched:
            if q not in state.topics_searched:
                state.topics_searched.append(q)

        state.all_results.extend(new_results)
        state.add_seen_urls([normalize_url(r.url) for r in new_results])

        successful = [
            r for r in new_results
            if r.full_text and not r.full_text.startswith("[Failed")
        ]
        if successful:
            await emit("extraction_start", {
                "hop": state.hop,
                "sources_with_content": len(successful),
            })
            batch_facts = await extract_facts(request.topic, successful)
            state.facts.extend(batch_facts)
            await emit("extraction_complete", {
                "hop": state.hop,
                "facts_extracted": len(batch_facts),
            })

        state.facts = await _verify_facts(request.topic, state.facts, emit)

        coverage = evaluate_coverage(
            request.topic,
            state.facts,
            hop=state.hop,
            max_hops=config.research_max_hops,
            coverage_threshold=config.research_coverage_threshold,
            sources_budget_remaining=request.max_sources - state.sources_fetched_count(),
            stagnant_hops=state.stagnant_hops,
        )
        state.last_coverage_score = coverage.score
        state.last_missing_dimensions = coverage.missing_dimensions

        expand_result = None
        if coverage.should_continue:
            expand_result = expand_queries(
                request.topic,
                coverage.gap_hints,
                candidates,
                hop=state.hop,
                facts=state.facts,
            )
            for hint in coverage.gap_hints:
                hint.suggested_queries = [
                    eq.query
                    for eq in expand_result.queries
                    if eq.dimension == hint.dimension
                ]
            state.pending_site_queries = [
                eq.query for eq in expand_result.queries if eq.channel == "site"
            ]
            state.pending_open_queries = [
                eq.query for eq in expand_result.queries if eq.channel == "open"
            ]
            # General topics: open-only expand (ignore site channel).
            if not candidates:
                state.pending_site_queries = []
                if not state.pending_open_queries:
                    state.pending_open_queries = [
                        eq.query for eq in expand_result.queries
                    ]
            state.pending_preferred_source_ids = preferred_source_ids_for_gaps(
                coverage.gap_hints
            ) if candidates else []

        # Hints for next hop include filled suggested_queries when expanding.
        state.coverage_hints = gap_hints_to_router_hints(coverage.gap_hints)
        coverage.suggested_router_hints = state.coverage_hints

        await emit("coverage_eval", {
            "hop": state.hop,
            "score": coverage.score,
            "covered": coverage.covered_dimensions,
            "missing": coverage.missing_dimensions,
            "should_continue": coverage.should_continue,
            "hints": coverage.suggested_router_hints,
            "gap_hints": [
                {
                    "dimension": h.dimension,
                    "research_goal": h.research_goal,
                    "suggested_queries": h.suggested_queries,
                }
                for h in coverage.gap_hints
            ],
            "unique_domains": coverage.unique_domains,
            "source_diversity_ok": coverage.source_diversity_ok,
        })

        if not coverage.should_continue or expand_result is None:
            break

        await emit("query_expand", {
            "hop": state.hop,
            "query_count": len(expand_result.queries),
            "capped": expand_result.capped,
            "queries": [
                {
                    "query": eq.query,
                    "channel": eq.channel,
                    "template_id": eq.template_id,
                    "research_goal": eq.research_goal,
                    "dimension": eq.dimension,
                }
                for eq in expand_result.queries
            ],
        })

        if len(state.facts) == prev_fact_count:
            state.stagnant_hops += 1
        else:
            state.stagnant_hops = 0
        prev_fact_count = len(state.facts)

        state.hop += 1

    unique_results = deduplicate_search_results(state.all_results)
    await emit("search_complete", {"results_found": len(unique_results)})
    await emit("dedup_complete", {
        "before": len(state.all_results),
        "after": len(unique_results),
        "removed": len(state.all_results) - len(unique_results),
    })

    await emit("report_start", {"fact_count": len(state.facts)})
    report_type = detect_report_type(request.topic)
    synthesis = await synthesize_report(
        request.topic,
        state.facts,
        state.topics_searched,
        report_type=report_type,
    )
    report = generate_report(
        request.topic,
        state.facts,
        started_at,
        synthesis=synthesis,
        topics_searched=state.topics_searched,
        fetched_results=unique_results,
        report_type=report_type,
    )
    await emit("report_complete", {
        "slug": report.slug,
        "citation_count": len(report.citations),
        "coverage_score": state.last_coverage_score,
    })
    return report
