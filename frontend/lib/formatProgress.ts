// D:/Projects/search-agent/frontend/lib/formatProgress.ts
import type { SSEEvent } from "./api";

export function formatProgressEvent(event: SSEEvent): string {
  const d = event.data || {};
  switch (event.event) {
    case "session_start":
      return `Session started (${d.mode || "quick"})`;
    case "dach_seeds_start":
      return `DACH seeds: ${d.seed_count} site: queries (${d.recency_days ?? 90}d window)`;
    case "catalog_filtered":
      return `Catalog: ${d.candidate_count} candidate sources (${(d.intent as string[])?.join(", ") || "general"})`;
    case "source_router_decision": {
      const hop = d.hop != null ? ` hop ${d.hop}` : "";
      const ids = (d.selected_source_ids as string[])?.join(", ") || "";
      return `Router${hop}: ${ids}${d.rationale ? ` — ${String(d.rationale).slice(0, 80)}` : ""}`;
    }
    case "direct_fetch":
      return `Direct fetch: ${d.url}`;
    case "coverage_eval": {
      const domains = d.unique_domains != null ? ` · ${d.unique_domains} domains` : "";
      return `Coverage hop ${d.hop}: ${Math.round(Number(d.score) * 100)}% (${(d.missing as string[])?.length || 0} gaps)${domains}`;
    }
    case "query_expand": {
      const site = (d.queries as { channel?: string }[])?.filter((q) => q.channel === "site").length ?? 0;
      const open = (d.queries as { channel?: string }[])?.filter((q) => q.channel === "open").length ?? 0;
      return `Query expand hop ${d.hop}: ${d.query_count} queries (${site} site, ${open} open)${d.capped ? " · capped" : ""}`;
    }
    case "open_search_forced":
      return `Open search forced: ${d.reason} (${d.unique_domains} domains)`;
    case "fetch_retry":
      return `Fetch retry: ${d.from} → ${d.to}`;
    case "fetch_failover":
      return `Fetch failover: ${d.from} → ${d.to}`;
    case "site_search_failover":
      return `Site search failover: ${String(d.from || "").slice(0, 40)} → ${String(d.to || "").slice(0, 40)}`;
    case "watch_run_start":
      return `Watch run: ${d.topic || d.watch_id}`;
    case "delta_ready":
      return `Delta ready: +${d.added} / −${d.removed} / ~${d.changed} (unchanged ${d.unchanged_count})`;
    case "watch_run_complete":
      return `Watch complete → ${d.slug}`;
    case "search_start":
      return `Searching: “${d.topic}”`;
    case "search_complete":
      return `Found ${d.results_found} sources`;
    case "fetch_fallback":
      return `Fetch fallback ${d.from} → ${d.to}`;
    case "dedup_complete":
      return `URL dedup: ${d.before} → ${d.after}`;
    case "extraction_start":
      return `Extracting from ${d.sources_with_content} pages`;
    case "extraction_complete":
      return `Extracted ${d.facts_extracted} facts`;
    case "fact_dedup_complete":
      return `Fact dedup: ${d.before} → ${d.after}`;
    case "verify_start":
      return `Verifying ${d.fact_count} facts…`;
    case "verify_complete": {
      const hop = d.hop ? ` (hop ${d.hop})` : "";
      return `Verified${hop}: ${d.after} facts, ${d.corroborated} corroborated`;
    }
    case "multihop_start":
      return `Follow-up hop ${d.hop}: ${(d.queries as string[])?.join(", ") || ""}`;
    case "multihop_complete":
      return `Hop ${d.hop} done: +${d.new_facts} facts`;
    case "plan_start":
      return `Planning deep research: ${d.dimension_count} dimensions`;
    case "plan_ready":
      return `Plan ready: ${d.title || "sections defined"}`;
    case "brief_ready":
      return `Brief ready: ${d.framework_id || "industry"} (${d.dimension_count || "?"} dims)`;
    case "brief_bound":
      return `Bound to brief: ${d.framework_id || ""}`;
    case "dimension_start":
      return `Dimension “${d.title}”: ${(d.queries as string[])?.length || 0} queries`;
    case "dimension_complete":
      return `“${d.title}”: ${d.results_found} results`;
    case "clarify_ready":
      return `Clarifying questions ready (${d.count} questions)`;
    case "report_start":
      return `Writing report (${d.fact_count} facts)`;
    case "report_complete":
    case "report_ready":
      return `Report ready: ${d.slug || "done"}`;
    case "report_content":
      return "Delivering report…";
    case "error":
      return `Error: ${d.message}`;
    default:
      return event.event;
  }
}
