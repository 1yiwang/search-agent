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
}

export interface MetaClarifyResponse {
  session_id: string;
  topic: string;
  questions: ClarifyingQuestion[];
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
  confidence: "high" | "medium" | "low";
}

export interface StructuredFinding {
  entity: string;
  signal: string;
  date: string;
  confidence: "high" | "medium" | "low";
  citation_index: number;
}

export interface ResearchReport {
  topic: string;
  slug: string;
  facts: ExtractedFact[];
  citations: Citation[];
  markdown: string;
  html_url: string;
  summary?: string;
  structured_findings?: StructuredFinding[];
  coverage?: string;
  gaps?: string;
  metadata?: {
    execution_time_seconds: number;
    source_count: number;
    topics_searched?: string[];
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
