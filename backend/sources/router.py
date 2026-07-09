"""LLM-constrained source router (Step 39)."""

from __future__ import annotations

import json
import re

from config import config
from llm_context import get_openai_client, get_request_keys
from sources.catalog import filter_candidates, get_source_by_id
from sources.models import RouterDecision, SourceEntry
from sources.seeds import build_combined_seed_queries

ROUTER_PROMPT = """You route a research topic to curated sources from a catalog.

Research topic: {topic}
Intent: {intent}
Coverage hints from prior pass (if any): {hints}

Candidate sources (pick ONLY from this list by id):
{catalog_json}

Instructions:
1. Select 3-6 source ids most relevant to the topic.
2. Propose up to {max_site_queries} site: search queries using selected domains — cover at least TWO different domains when candidates allow.
3. Propose up to {max_direct_urls} direct URLs ONLY from entry_urls of selected sources (or empty). Prefer URLs from multiple domains, not only one site.
4. Set defer_open_web true only if curated multi-domain sources should suffice this round.
5. One-sentence rationale.

Return ONLY valid JSON:
```json
{{
  "selected_source_ids": ["id1", "id2"],
  "direct_url_fetches": ["https://..."],
  "site_queries": ["site:domain.com topic keywords"],
  "rationale": "...",
  "defer_open_web": false
}}
```"""


def _compact_topic(topic: str, max_words: int = 8) -> str:
    words = topic.split()
    if len(words) <= max_words:
        return topic.strip()
    return " ".join(words[:max_words])


def _parse_router_json(content: str) -> dict:
    content = (content or "").strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
        if content.endswith("```"):
            content = content[:-3].strip()
    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _allowed_domains(selected_ids: list[str]) -> set[str]:
    domains: set[str] = set()
    for sid in selected_ids:
        entry = get_source_by_id(sid)
        if entry:
            domains.add(entry.domain.lower())
            domains.add(entry.domain.lower().removeprefix("www."))
    return domains


def _url_domain_allowed(url: str, allowed_domains: set[str]) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if not host:
        return False
    for domain in allowed_domains:
        d = domain.removeprefix("www.")
        if host == d or host.endswith("." + d):
            return True
    return False


def _enforce_constraints(
    raw: dict,
    candidates: list[SourceEntry],
    topic: str,
) -> RouterDecision:
    candidate_ids = {c.id for c in candidates}
    selected = [sid for sid in (raw.get("selected_source_ids") or []) if sid in candidate_ids]
    selected = selected[: config.router_max_sources_per_round]

    if not selected and candidates:
        selected = [c.id for c in candidates[:3]]

    allowed_domains = _allowed_domains(selected)
    allowed_entry_urls: set[str] = set()
    for sid in selected:
        entry = get_source_by_id(sid)
        if entry:
            allowed_entry_urls.update(entry.entry_urls)

    direct_urls: list[str] = []
    for url in raw.get("direct_url_fetches") or []:
        url = str(url).strip()
        if not url:
            continue
        if url in allowed_entry_urls or _url_domain_allowed(url, allowed_domains):
            if url not in direct_urls:
                direct_urls.append(url)
        if len(direct_urls) >= config.router_max_direct_fetches:
            break

    site_queries: list[str] = []
    compact = _compact_topic(topic)
    for q in raw.get("site_queries") or []:
        q = str(q).strip()
        if q and q not in site_queries:
            site_queries.append(q)
        if len(site_queries) >= config.router_max_site_queries:
            break

    if not site_queries:
        for sid in selected:
            entry = get_source_by_id(sid)
            if not entry:
                continue
            for template in entry.search_templates[:1]:
                site_queries.append(template.replace("{topic}", compact))
            if len(site_queries) >= config.router_max_site_queries:
                break

    # Ensure site queries span at least two distinct domains when possible
    if len(site_queries) < 2 and len(selected) >= 2:
        seen_domains: set[str] = set()
        for q in site_queries:
            m = re.search(r"site:([^\s]+)", q, re.I)
            if m:
                seen_domains.add(m.group(1).lower().removeprefix("www."))
        for sid in selected:
            entry = get_source_by_id(sid)
            if not entry:
                continue
            domain = entry.domain.lower().removeprefix("www.")
            if domain in seen_domains:
                continue
            site_queries.append(f"site:{domain} {compact}")
            seen_domains.add(domain)
            if len(site_queries) >= 2:
                break

    return RouterDecision(
        selected_source_ids=selected,
        direct_url_fetches=direct_urls,
        site_queries=site_queries,
        rationale=str(raw.get("rationale") or "").strip(),
        defer_open_web=bool(raw.get("defer_open_web")),
        fallback=False,
    )


def fallback_decision(topic: str, candidates: list[SourceEntry]) -> RouterDecision:
    """Deterministic routing when LLM unavailable or router disabled."""
    selected = [c.id for c in candidates[: config.router_max_sources_per_round]]
    compact = _compact_topic(topic)

    site_queries = build_combined_seed_queries(topic, max_seeds=config.router_max_site_queries)
    if not site_queries:
        for sid in selected:
            entry = get_source_by_id(sid)
            if entry and entry.search_templates:
                site_queries.append(entry.search_templates[0].replace("{topic}", compact))

    direct_urls: list[str] = []
    for sid in selected:
        entry = get_source_by_id(sid)
        if entry:
            for url in entry.entry_urls[:1]:
                if url not in direct_urls:
                    direct_urls.append(url)
        if len(direct_urls) >= config.router_max_direct_fetches:
            break

    return RouterDecision(
        selected_source_ids=selected,
        direct_url_fetches=direct_urls,
        site_queries=site_queries[: config.router_max_site_queries],
        rationale="Fallback: keyword-ranked catalog sources and seed queries.",
        defer_open_web=False,
        fallback=True,
    )


async def route_sources(
    topic: str,
    coverage_hints: list[str] | None = None,
    *,
    candidates: list[SourceEntry] | None = None,
) -> RouterDecision:
    """LLM picks sources from pre-filtered catalog; enforces hard constraints."""
    if candidates is None:
        candidates = filter_candidates(topic)

    if not config.router_enabled or not candidates:
        return fallback_decision(topic, candidates)

    keys = get_request_keys()
    if not keys or not keys.llm_api_key:
        return fallback_decision(topic, candidates)

    from sources.catalog import catalog_summary_for_llm, intent_labels

    try:
        response = await get_openai_client().chat.completions.create(
            model=keys.llm_model,
            messages=[{
                "role": "user",
                "content": ROUTER_PROMPT.format(
                    topic=topic,
                    intent=", ".join(intent_labels(topic)),
                    hints=", ".join(coverage_hints or []) or "none",
                    catalog_json=json.dumps(
                        catalog_summary_for_llm(candidates),
                        ensure_ascii=False,
                        indent=2,
                    ),
                    max_site_queries=config.router_max_site_queries,
                    max_direct_urls=config.router_max_direct_fetches,
                ),
            }],
            temperature=0.2,
            max_tokens=1024,
        )
        raw = _parse_router_json(response.choices[0].message.content or "")
        return _enforce_constraints(raw, candidates, topic)
    except Exception:
        return fallback_decision(topic, candidates)
