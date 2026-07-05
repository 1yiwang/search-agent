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
        setProgress((prev) => [...prev, formatProgressEvent(event)]);

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
    <main className="mx-auto max-w-3xl px-4 py-16 md:py-24">
      <header className="mb-10 text-center">
        <p className="mb-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
          Verifiable research
        </p>
        <h1 className="font-display text-4xl md:text-5xl text-[var(--ink)]">
          Search Agent
        </h1>
        <p className="mt-3 text-[var(--muted)] max-w-md mx-auto">
          You define the question. We search, extract, and cite every claim.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-5">
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="What do you want to research?"
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)]
                     px-5 py-4 text-lg text-[var(--ink)]
                     placeholder:text-[var(--muted)] focus:border-[var(--accent-dim)]
                     focus:outline-none focus:ring-1 focus:ring-[var(--accent-dim)]"
          disabled={loading}
        />

        <div className="flex items-center justify-center gap-8 text-sm">
          <label className="flex items-center gap-2 cursor-pointer text-[var(--ink)]">
            <input
              type="radio"
              name="mode"
              value="quick"
              checked={mode === "quick"}
              onChange={() => setMode("quick")}
              className="accent-[var(--accent)]"
            />
            <span>Quick search</span>
          </label>
          <label className="flex items-center gap-2 cursor-not-allowed opacity-40 text-[var(--muted)]">
            <input
              type="radio"
              name="mode"
              value="deep"
              disabled
              className="accent-[var(--accent)]"
            />
            <span>Deep planning (Wave 2)</span>
          </label>
        </div>

        <div className="text-center pt-2">
          <button
            type="submit"
            disabled={loading || !topic.trim()}
            className="rounded-lg bg-[var(--accent)] px-10 py-3 font-semibold text-[#1a1408]
                       hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all"
          >
            {loading ? "Researching…" : "Start research"}
          </button>
        </div>
      </form>

      {progress.length > 0 && (
        <div className="mt-10 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Progress
          </h2>
          <ol className="max-h-56 overflow-y-auto space-y-2 text-sm">
            {progress.map((line, i) => (
              <li
                key={i}
                className={`progress-line text-[var(--muted)] ${
                  i === progress.length - 1 && loading ? "progress-line-active text-[var(--ink)]" : ""
                }`}
              >
                {line}
              </li>
            ))}
          </ol>
        </div>
      )}

      {result && (
        <div className="mt-10 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-2xl text-[var(--ink)]">Research complete</h2>
            <span className="text-sm text-[var(--muted)]">
              {result.fact_count} facts ·{" "}
              <a
                href={`/research/${result.slug}`}
                className="text-[var(--link)] hover:underline"
              >
                Open report →
              </a>
            </span>
          </div>
          <pre className="whitespace-pre-wrap text-sm text-[var(--muted)] font-mono leading-relaxed max-h-64 overflow-y-auto">
            {result.markdown.slice(0, 2000)}
            {result.markdown.length > 2000 && "\n\n… (preview truncated)"}
          </pre>
        </div>
      )}
    </main>
  );
}

function formatProgressEvent(event: SSEEvent): string {
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
