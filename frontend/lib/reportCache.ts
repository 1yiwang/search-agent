/** Browser cache for reports so Saved reports / report pages work when personal API is offline. */

import type { ReportSummary, ResearchReport } from "@/lib/api";

const INDEX_KEY = "sa_report_index_v1";
const reportKey = (slug: string) => `sa_report_v1:${slug}`;
const MAX_CACHED = 40;

function readIndex(): ReportSummary[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(INDEX_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ReportSummary[]) : [];
  } catch {
    return [];
  }
}

function writeIndex(items: ReportSummary[]) {
  localStorage.setItem(INDEX_KEY, JSON.stringify(items.slice(0, MAX_CACHED)));
}

export function listCachedReports(limit = 50): ReportSummary[] {
  return readIndex().slice(0, limit);
}

export function getCachedReport(slug: string): ResearchReport | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(reportKey(slug));
    if (!raw) return null;
    return JSON.parse(raw) as ResearchReport;
  } catch {
    return null;
  }
}

export function cacheReport(report: ResearchReport): void {
  if (typeof window === "undefined" || !report?.slug) return;
  try {
    const summary: ReportSummary = {
      slug: report.slug,
      topic: report.topic,
      fact_count: report.facts?.length ?? 0,
      completed_at: report.metadata?.completed_at || "",
      html_url: report.html_url || "",
    };
    localStorage.setItem(reportKey(report.slug), JSON.stringify(report));
    const rest = readIndex().filter((r) => r.slug !== report.slug);
    writeIndex([summary, ...rest]);
  } catch {
    // Quota or private mode — ignore
  }
}

export function isApiOfflineError(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m.includes("offline") ||
    m.includes("start backend") ||
    m.includes("start personal") ||
    m.includes("tunnel") ||
    m.includes("503") ||
    m.includes("502") ||
    m.includes("504")
  );
}
