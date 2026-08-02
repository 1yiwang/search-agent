"""Coverage-driven research loop with Source Router (Step 40)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from config import config
from coverage import evaluate_coverage
from dedup import deduplicate_facts, deduplicate_search_results, normalize_url
from depth_profile import depth_overrides, resolve_request
from extraction import extract_facts
from brief import (
    brief_direction_queries,
    brief_gap_dimension_ids,
    brief_seed_queries,
    filter_queries_by_deprioritize,
)
from models import ExtractedFact, ResearchBrief, ResearchRequest, ResearchReport
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


def _brief_coverage_dims(
    brief: ResearchBrief,
) -> list[tuple[str, str, list[str]]]:
    from text_tokens import keyword_list

    ids = brief_gap_dimension_ids(brief)
    out: list[tuple[str, str, list[str]]] = []
    for dim_id, dim in zip(ids, brief.dimensions):
        goal = dim.research_goal or ""
        keywords = keyword_list(
            dim.title,
            goal,
            dim.direction_detail,
            " ".join(dim.entities or []),
            max_tokens=16,
        )
        if not keywords and dim.title:
            keywords = [dim.title.lower()]
        out.append((dim_id, goal or dim.title, keywords))
    return out


async def run_research_loop(
    request: ResearchRequest,
    event_callback: EmitCallback | None = None,
    brief: ResearchBrief | None = None,
) -> ResearchReport:
    """Execute coverage-driven search → extract → verify → report."""
    started_at = datetime.now(timezone.utc)
    request, profile = resolve_request(request)

    async def emit(event_type: str, data: dict) -> None:
        if event_callback:
            await event_callback(event_type, data)

    with depth_overrides(profile):
        return await _run_research_loop_body(
            request, profile.name, started_at, emit, brief=brief,
        )


async def _run_research_loop_body(
    request: ResearchRequest,
    depth_name: str,
    started_at: datetime,
    emit: EmitCallback,
    brief: ResearchBrief | None = None,
) -> ResearchReport:
    state = ResearchState(
        topic=request.topic,
        max_sources=request.max_sources,
        topics_searched=[request.topic],
    )
    seen_urls: set[str] = set()
    brief_dims = _brief_coverage_dims(brief) if brief else None
    deprioritize = list(brief.deprioritize) if brief else []

    await emit("search_start", {
        "topic": request.topic,
        "max_sources": request.max_sources,
        "depth": depth_name,
        "router_enabled": config.router_enabled,
        "brief_bound": brief is not None,
        "framework_id": brief.framework_id if brief else None,
    })
    if brief:
        await emit("brief_bound", {
            "framework_id": brief.framework_id,
            "dimension_count": len(brief.dimensions),
            "deprioritize": (brief.deprioritize or [])[:8],
            "problem_restatement": (brief.problem_restatement or "")[:300],
        })

    candidates = filter_candidates(request.topic)
    await emit("catalog_filtered", {
        "candidate_count": len(candidates),
        "intent": intent_labels(request.topic),
    })

    # Seed pending open queries from brief on hop 0
    if brief:
        state.pending_open_queries = brief_seed_queries(brief)
        await emit("direction_plan", {
            "directions": [
                {
                    "direction_id": d.direction_id or d.phase_id or d.title,
                    "title": d.title,
                    "goal": d.research_goal,
                    "entities": (d.entities or [])[:8],
                    "must_answer": (d.must_answer or [])[:4],
                    "budget_weight": d.budget_weight,
                    "query_count": len(d.queries),
                }
                for d in brief.dimensions[:8]
            ],
            "seed_queries": state.pending_open_queries[:12],
        })
        await emit("direction_budget", {
            "weights": {
                (d.direction_id or d.phase_id or d.title): d.budget_weight
                for d in brief.dimensions
            },
            "seed_query_count": len(state.pending_open_queries),
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
            or brief is not None
            or (state.hop == 0 and not decision.defer_open_web)
            or bool(state.pending_open_queries)
            or (not state.facts and state.hop > 0)
        )
        open_q = state.pending_open_queries or (
            initial_open_queries(request.topic, hop=state.hop)
            if (is_general or force_open) and not brief
            else None
        )
        if open_q and deprioritize:
            open_q = filter_queries_by_deprioritize(open_q, deprioritize)

        new_results, searched, leftover_open = await execute_router_decision(
            request.topic,
            decision,
            seen_urls,
            budget_remaining=budget_remaining,
            event_callback=emit,
            force_open_web=force_open,
            open_queries=open_q,
            missing_dimensions=state.last_missing_dimensions or None,
            gap_hop=state.hop > 0 and (
                bool(state.last_missing_dimensions) or not state.facts
            ),
        )
        # Re-queue open queries the executor could not run this hop (budget slice).
        state.pending_open_queries = list(leftover_open or [])
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
            brief_dimensions=brief_dims,
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
            site_q = [
                eq.query for eq in expand_result.queries if eq.channel == "site"
            ]
            open_pending = [
                eq.query for eq in expand_result.queries if eq.channel == "open"
            ]
            if deprioritize:
                site_q = filter_queries_by_deprioritize(site_q, deprioritize)
                open_pending = filter_queries_by_deprioritize(open_pending, deprioritize)
            # Keep unexecuted leftovers ahead of freshly expanded opens.
            leftover_keep = list(state.pending_open_queries)
            state.pending_site_queries = site_q
            state.pending_open_queries = leftover_keep + [
                q for q in open_pending if q not in leftover_keep
            ]
            # General topics: open-only expand (ignore site channel).
            if not candidates:
                state.pending_site_queries = []
                if not state.pending_open_queries:
                    state.pending_open_queries = filter_queries_by_deprioritize(
                        [eq.query for eq in expand_result.queries],
                        deprioritize,
                    ) if deprioritize else [eq.query for eq in expand_result.queries]
            # Brief A′: prioritize queries for missing directions (code-driven)
            if brief and coverage.missing_dimensions:
                directed = brief_direction_queries(
                    brief, coverage.missing_dimensions, max_queries=8,
                )
                merged = directed + [
                    q for q in state.pending_open_queries if q not in directed
                ]
                state.pending_open_queries = merged[:12]
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
        brief=brief,
        event_callback=emit,
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
