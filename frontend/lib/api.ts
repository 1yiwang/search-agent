// D:/Projects/search-agent/frontend/lib/api.ts

import { authHeaders } from "./auth";
import { getApiBase } from "./apiBase";
import { loadSettings, settingsHeaders } from "./settings";

function getRequestHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...settingsHeaders(loadSettings()),
  };
}

export async function checkApiHealth(): Promise<{
  ok: boolean;
  apiAuthRequired?: boolean;
}> {
  try {
    const res = await fetch(`${getApiBase()}/api/health`, { cache: "no-store" });
    if (!res.ok) return { ok: false };
    const data = await res.json();
    return {
      ok: data.status === "ok",
      apiAuthRequired: Boolean(data.api_auth_required),
    };
  } catch {
    return { ok: false };
  }
}

export interface ResearchRequest {
  topic: string;
  max_sources?: number;
  /** fast | standard | deep — Wave 10 Step 62 */
  depth?: "fast" | "standard" | "deep";
  brief_session_id?: string;
}

export interface DeepResearchRequest {
  topic: string;
  max_sections?: number;
  initial_sources?: number;
  sources_per_query?: number;
}

export interface ClarifyingQuestion {
  id: string;
  question: string;
  hint?: string;
  category?: string;
  options?: string[];
}

export interface MetaClarifyResponse {
  session_id: string;
  topic: string;
  questions: ClarifyingQuestion[];
}

export interface BriefClarifyResponse {
  session_id: string;
  topic: string;
  questions: ClarifyingQuestion[];
  suggested_framework_id: string;
}

export interface BriefDimension {
  title: string;
  research_goal: string;
  queries: string[];
  priority: number;
  info_type: string;
  phase_id?: string;
}

export interface ResearchBrief {
  topic: string;
  problem_restatement: string;
  framework_id: string;
  clarify_answers: Record<string, string>;
  phases: Array<{ id?: string; title?: string; goal?: string }>;
  dimensions: BriefDimension[];
  deprioritize: string[];
  source_prefs: string[];
  success_criteria: string[];
  assumed_defaults: string[];
  overview_markdown: string;
  confirmed: boolean;
}

export interface ResearchDimension {
  title: string;
  queries: string[];
  priority: number;
  info_type: string;
}

export interface ResearchPlan {
  topic: string;
  title: string;
  date: string;
  initial_research_summary: string;
  dimensions: ResearchDimension[];
  max_sections: number;
}

export interface Citation {
  index: number;
  source_name: string;
  source_url: string;
  quoted_text: string;
  highlight_anchor: string;
}

export interface ExtractedFact {
  fact: string;
  source_url: string;
  source_title: string;
  quoted_text: string;
  event_date?: string;
  confidence: "high" | "medium" | "low";
  signal_type?: string;
  entity_type?: string;
}

export interface StructuredFinding {
  entity: string;
  signal: string;
  date: string;
  confidence: "high" | "medium" | "low";
  citation_index: number;
  signal_type?: string;
  entity_type?: string;
}

export interface ReportArgument {
  claim: string;
  detail?: string;
  citation_indices: number[];
  confidence?: "high" | "medium" | "low";
}

export interface SourceSnapshot {
  url: string;
  title: string;
  content_kind: "html" | "document" | "empty";
  text: string;
  normalized_url?: string;
}

export interface ResearchReport {
  topic: string;
  slug: string;
  report_type?: "intelligence_brief" | "investor_brief";
  facts: ExtractedFact[];
  citations: Citation[];
  markdown: string;
  html_url: string;
  thesis?: string;
  arguments?: ReportArgument[];
  summary?: string;
  structured_findings?: StructuredFinding[];
  coverage?: string;
  gaps?: string;
  fund_activity?: string;
  credit_risk_watch?: string;
  source_snapshots?: SourceSnapshot[];
  metadata?: {
    execution_time_seconds: number;
    source_count: number;
    topics_searched?: string[];
    started_at?: string;
    completed_at?: string;
  };
}

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

async function apiFetch(path: string, init: RequestInit): Promise<Response> {
  const base = getApiBase();
  const url = `${base}${path}`;
  try {
    return await fetch(url, init);
  } catch (err) {
    const hint = base
      ? `Cannot reach ${base}. Start backend + tunnel (scripts/start-tunnel.ps1).`
      : "Cannot reach API. Start backend on :8000 or set NEXT_PUBLIC_API_URL.";
    const msg = err instanceof Error ? err.message : "Network error";
    throw new Error(`${msg} — ${hint}`);
  }
}

async function* parseSSEStream(response: Response): AsyncGenerator<SSEEvent> {
  if (response.status === 401) {
    throw new Error("Unauthorized — log out and sign in again to refresh API token.");
  }
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}): ${response.statusText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ") && line !== "data: [DONE]") {
        try {
          yield JSON.parse(line.slice(6)) as SSEEvent;
        } catch {
          // skip parse errors
        }
      }
    }
  }
}

export async function* streamResearch(
  request: ResearchRequest
): AsyncGenerator<SSEEvent> {
  const response = await apiFetch("/api/research/stream", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify(request),
  });
  yield* parseSSEStream(response);
}

export async function* streamDeepResearch(
  request: DeepResearchRequest
): AsyncGenerator<SSEEvent> {
  const response = await apiFetch("/api/research/deep/stream", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify({
      max_sections: 4,
      initial_sources: 5,
      sources_per_query: 3,
      ...request,
    }),
  });
  yield* parseSSEStream(response);
}

export async function metaClarify(topic: string): Promise<MetaClarifyResponse> {
  const response = await apiFetch("/api/meta/clarify", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify({ topic }),
  });
  if (!response.ok) {
    throw new Error(`Clarify failed: ${response.statusText}`);
  }
  return response.json();
}

export async function metaPlan(params: {
  session_id: string;
  answers?: Record<string, string>;
  feedback?: string;
  max_sections?: number;
  initial_sources?: number;
}): Promise<ResearchPlan> {
  const response = await apiFetch("/api/meta/plan", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    throw new Error(`Plan failed: ${response.statusText}`);
  }
  return response.json();
}

export async function* streamMetaResearch(params: {
  session_id: string;
  sources_per_query?: number;
}): AsyncGenerator<SSEEvent> {
  const response = await apiFetch("/api/meta/research/stream", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify({
      sources_per_query: 3,
      ...params,
    }),
  });
  yield* parseSSEStream(response);
}

export async function briefClarify(topic: string): Promise<BriefClarifyResponse> {
  const response = await apiFetch("/api/brief/clarify", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify({ topic }),
  });
  if (!response.ok) {
    throw new Error(`Brief clarify failed: ${response.statusText}`);
  }
  return response.json();
}

export async function briefGenerate(params: {
  session_id: string;
  answers?: Record<string, string>;
  framework_id?: string;
}): Promise<ResearchBrief> {
  const response = await apiFetch("/api/brief/generate", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    throw new Error(`Brief generate failed: ${response.statusText}`);
  }
  return response.json();
}

export async function briefRevise(params: {
  session_id: string;
  feedback: string;
}): Promise<ResearchBrief> {
  const response = await apiFetch("/api/brief/revise", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    throw new Error(`Brief revise failed: ${response.statusText}`);
  }
  return response.json();
}

export async function briefConfirm(session_id: string): Promise<ResearchBrief> {
  const response = await apiFetch("/api/brief/confirm", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify({ session_id }),
  });
  if (!response.ok) {
    throw new Error(`Brief confirm failed: ${response.statusText}`);
  }
  return response.json();
}

export async function* streamBriefResearch(params: {
  session_id: string;
  depth?: "fast" | "standard" | "deep";
  max_sources?: number;
}): AsyncGenerator<SSEEvent> {
  const response = await apiFetch("/api/brief/research/stream", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify({
      depth: "standard",
      ...params,
    }),
  });
  yield* parseSSEStream(response);
}

export async function getReport(slug: string): Promise<ResearchReport> {
  const response = await fetch(`/api/research/${encodeURIComponent(slug)}`, {
    cache: "no-store",
    credentials: "include",
    headers: authHeaders(),
  });
  if (response.status === 401) {
    throw new Error("Not signed in — log in again to view reports.");
  }
  if (response.status === 503) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      String(data.error || "Personal API offline — start backend + tunnel."),
    );
  }
  if (!response.ok) {
    throw new Error(`Report not found: ${slug}`);
  }
  return response.json();
}

export interface ReportSummary {
  slug: string;
  topic: string;
  fact_count: number;
  completed_at: string;
  html_url: string;
}

export async function listReports(limit = 30): Promise<ReportSummary[]> {
  const response = await fetch(`/api/reports?limit=${limit}`, {
    cache: "no-store",
    credentials: "include",
    headers: authHeaders(),
  });
  if (response.status === 401) {
    throw new Error("Not signed in — log in again to view saved reports.");
  }
  if (response.status === 503) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      String(data.error || "Personal API offline — start backend + tunnel."),
    );
  }
  if (!response.ok) {
    throw new Error("Failed to load saved reports");
  }
  const data = await response.json();
  return (data.reports ?? []) as ReportSummary[];
}

export interface WatchItem {
  id: string;
  topic: string;
  max_sources: number;
  cadence: "manual" | "weekly";
  enabled: boolean;
  baseline_slug: string;
  latest_slug: string;
  last_run_at: string;
  created_at: string;
  recency_days: number;
  latest_delta_id: string;
}

export interface DeltaFinding {
  key: string;
  entity: string;
  signal: string;
  signal_type: string;
  date: string;
  confidence: string;
  citation_index: number;
  fact: string;
  source_url: string;
  change_note: string;
}

export interface WatchDelta {
  watch_id: string;
  run_id: string;
  prev_slug: string;
  curr_slug: string;
  created_at: string;
  added: DeltaFinding[];
  removed: DeltaFinding[];
  changed: DeltaFinding[];
  unchanged_count: number;
  summary_markdown: string;
}

export async function listWatches(): Promise<WatchItem[]> {
  const response = await apiFetch("/api/watchlist", {
    method: "GET",
    headers: getRequestHeaders(),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load watchlist (${response.status})`);
  }
  return response.json();
}

export async function createWatch(payload: {
  topic: string;
  max_sources?: number;
  cadence?: "manual" | "weekly";
  recency_days?: number;
  baseline_slug?: string;
}): Promise<WatchItem> {
  const response = await apiFetch("/api/watchlist", {
    method: "POST",
    headers: getRequestHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Create watch failed (${response.status})`);
  }
  return response.json();
}

export async function deleteWatch(watchId: string): Promise<void> {
  const response = await apiFetch(`/api/watchlist/${encodeURIComponent(watchId)}`, {
    method: "DELETE",
    headers: getRequestHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Delete watch failed (${response.status})`);
  }
}

export async function getLatestWatchDelta(watchId: string): Promise<WatchDelta | null> {
  const response = await apiFetch(
    `/api/watchlist/${encodeURIComponent(watchId)}/delta/latest`,
    { method: "GET", headers: getRequestHeaders(), cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Failed to load delta (${response.status})`);
  }
  return response.json();
}

export async function* streamWatchRun(watchId: string): AsyncGenerator<SSEEvent> {
  const response = await apiFetch(
    `/api/watchlist/${encodeURIComponent(watchId)}/run/stream`,
    { method: "POST", headers: getRequestHeaders() },
  );
  yield* parseSSEStream(response);
}
