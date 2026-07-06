import type { SSEEvent } from "./api";

/** Build client route for a saved report slug. */
export function researchReportPath(slug: string): string {
  return `/research/${encodeURIComponent(slug)}`;
}

/** Read slug from report_ready SSE event, if present. */
export function slugFromReportReady(event: SSEEvent): string | null {
  if (event.event !== "report_ready" || !event.data?.slug) return null;
  return String(event.data.slug);
}
