// D:/Projects/search-agent/frontend/app/page.tsx
"use client";

import { useState } from "react";
import { streamResearch, type SSEEvent } from "@/lib/api";

type Mode = "quick" | "deep";

export default function SearchPage() {
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<Mode>("quick");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [result, setResult] = useState<{
    slug: string;
    markdown: string;
    fact_count: number;
  } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || loading) return;

    setLoading(true);
    setProgress([]);
    setResult(null);

    const events: SSEEvent[] = [];
    try {
      for await (const event of streamResearch({
        topic: topic.trim(),
        max_sources: 10,
      })) {
        events.push(event);
        const label = EVENT_LABELS[event.event] || event.event;
        setProgress((prev) => [...prev, `${label}: ${JSON.stringify(event.data)}`]);

        if (event.event === "report_ready" && event.data) {
          // Don't set result yet, wait for report_content
        }
        if (event.event === "report_content" && event.data) {
          const data = event.data as { markdown: string };
          const readyEvent = events.find((e) => e.event === "report_ready");
          const readyData = (readyEvent?.data || {}) as {
            slug: string;
            fact_count: number;
          };
          setResult({
            slug: readyData.slug || "unknown",
            markdown: data.markdown || "",
            fact_count: readyData.fact_count || 0,
          });
        }
      }
    } catch (err) {
      setProgress((prev) => [
        ...prev,
        `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-20">
      <h1 className="mb-2 text-center text-3xl font-bold tracking-tight">
        🔍 Search Agent
      </h1>
      <p className="mb-8 text-center text-zinc-400">
        Controllable, verifiable deep research — you keep thinking, we execute.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="What do you want to research?"
          className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-4 text-lg
                     placeholder:text-zinc-500 focus:border-zinc-500 focus:outline-none"
          disabled={loading}
        />

        <div className="flex items-center justify-center gap-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="mode"
              value="quick"
              checked={mode === "quick"}
              onChange={() => setMode("quick")}
              className="accent-zinc-400"
            />
            <span>⚡ Quick Search</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer opacity-50">
            <input
              type="radio"
              name="mode"
              value="deep"
              disabled
              className="accent-zinc-400"
            />
            <span>🧠 Deep Planning (Phase 2)</span>
          </label>
        </div>

        <div className="text-center">
          <button
            type="submit"
            disabled={loading || !topic.trim()}
            className="rounded-xl bg-zinc-100 px-8 py-3 font-semibold text-zinc-900
                       hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
          >
            {loading ? "Researching..." : "Start Research"}
          </button>
        </div>
      </form>

      {progress.length > 0 && (
        <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <h2 className="mb-2 font-semibold text-zinc-300">Progress</h2>
          <div className="max-h-48 overflow-y-auto space-y-1 text-sm text-zinc-500">
            {progress.map((p, i) => (
              <div key={i}>{p}</div>
            ))}
          </div>
        </div>
      )}

      {result && (
        <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">Research Complete</h2>
            <span className="text-sm text-zinc-500">
              {result.fact_count} facts ·{" "}
              <a
                href={`/research/${result.slug}`}
                className="text-blue-400 hover:underline"
              >
                View report →
              </a>
            </span>
          </div>
          <div className="prose prose-invert prose-zinc max-w-none">
            <pre className="whitespace-pre-wrap text-sm text-zinc-400 font-mono">
              {result.markdown.slice(0, 2000)}
              {result.markdown.length > 2000 && "\n\n... (truncated preview)"}
            </pre>
          </div>
        </div>
      )}
    </main>
  );
}

const EVENT_LABELS: Record<string, string> = {
  search_start: "🔍 Searching",
  search_complete: "✅ Search done",
  dedup_complete: "🔄 Deduplication",
  extraction_start: "🧠 Extracting facts",
  extraction_complete: "✅ Extraction done",
  fact_dedup_complete: "🔄 Fact dedup",
  report_start: "📝 Generating report",
  report_complete: "✅ Report ready",
  report_ready: "📄 Report ready",
  report_content: "📄 Report content",
};
