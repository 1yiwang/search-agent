// D:/Projects/search-agent/frontend/lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export interface ResearchReport {
  topic: string;
  slug: string;
  facts: ExtractedFact[];
  citations: Citation[];
  markdown: string;
  html_url: string;
  metadata?: {
    execution_time_seconds: number;
    source_count: number;
  };
}

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

async function* parseSSEStream(response: Response): AsyncGenerator<SSEEvent> {
  if (!response.ok) {
    throw new Error(`Request failed: ${response.statusText}`);
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
  const response = await fetch(`${API_BASE}/api/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  yield* parseSSEStream(response);
}

export async function* streamDeepResearch(
  request: DeepResearchRequest
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_BASE}/api/research/deep/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const response = await fetch(`${API_BASE}/api/meta/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const response = await fetch(`${API_BASE}/api/meta/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const response = await fetch(`${API_BASE}/api/meta/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sources_per_query: 3,
      ...params,
    }),
  });
  yield* parseSSEStream(response);
}

export async function getReport(slug: string): Promise<ResearchReport> {
  const response = await fetch(`${API_BASE}/api/research/${slug}`);
  if (!response.ok) {
    throw new Error(`Report not found: ${slug}`);
  }
  return response.json();
}
