// D:/Projects/search-agent/frontend/lib/formatProgress.ts
import type { SSEEvent } from "./api";

export function formatProgressEvent(event: SSEEvent): string {
  const d = event.data || {};
  switch (event.event) {
    case "session_start":
      return `Session started (${d.mode || "quick"})`;
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
