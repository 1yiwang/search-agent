// D:/Projects/search-agent/frontend/lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ResearchRequest {
  topic: string;
  max_sources?: number;
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

export async function* streamResearch(
  request: ResearchRequest
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_BASE}/api/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Research failed: ${response.statusText}`);
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
          const event: SSEEvent = JSON.parse(line.slice(6));
          yield event;
        } catch {
          // skip parse errors
        }
      }
    }
  }
}

export async function getReport(slug: string): Promise<ResearchReport> {
  const response = await fetch(`${API_BASE}/api/research/${slug}`);
  if (!response.ok) {
    throw new Error(`Report not found: ${slug}`);
  }
  return response.json();
}
