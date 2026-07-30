"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  streamResearch,
  streamDeepResearch,
  checkApiHealth,
  type SSEEvent,
} from "@/lib/api";
import { formatProgressEvent } from "@/lib/formatProgress";
import { getApiToken } from "@/lib/auth";
import { loadSettings } from "@/lib/settings";
import { researchReportPath, slugFromReportReady } from "@/lib/researchNav";
import { ApiStatus } from "@/components/ApiStatus";
import { SettingsPanel } from "@/components/SettingsPanel";

type Mode = "quick" | "deep";

export default function SearchPage() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<Mode>("quick");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || loading) return;

    setLoading(true);
    setProgress([]);

    const health = await checkApiHealth();
    if (!health.ok) {
      setProgress(["Error: API offline — start backend on :8000 first."]);
      setLoading(false);
      return;
    }
    // Token only required when backend has API_AUTH_SECRET (Mode B local often has none).
    if (health.apiAuthRequired && !getApiToken()) {
      setProgress([
        "Error: API requires login — open /login, enter site password, then retry.",
      ]);
      setLoading(false);
      return;
    }
    if (!loadSettings().llmApiKey.trim()) {
      setProgress(["Error: Add your LLM API key in Settings before researching."]);
      setLoading(false);
      return;
    }

    const events: SSEEvent[] = [];
    try {
      const stream =
        mode === "deep"
          ? streamDeepResearch({ topic: topic.trim(), max_sections: 4 })
          : streamResearch({ topic: topic.trim(), max_sources: 10 });

      for await (const event of stream) {
        events.push(event);
        setProgress((prev) => [...prev, formatProgressEvent(event)]);

        const slug = slugFromReportReady(event);
        if (slug) {
          router.push(researchReportPath(slug));
        }
      }

      const fallbackSlug = events
        .map(slugFromReportReady)
        .find((s): s is string => Boolean(s));
      if (fallbackSlug) {
        router.push(researchReportPath(fallbackSlug));
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
        <div className="mt-4 flex flex-col items-center gap-2">
          <ApiStatus />
          <SettingsPanel />
          <Link href="/history" className="text-sm text-[var(--link)] hover:underline">
            Saved reports
          </Link>
          <Link href="/watchlist" className="text-sm text-[var(--link)] hover:underline">
            Watchlist
          </Link>
        </div>
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

        <div className="flex flex-wrap justify-center gap-2 text-sm">
          <button
            type="button"
            disabled={loading}
            onClick={() =>
              setTopic(
                "European corporate direct lending fundraising and deployment trends H1 2026"
              )
            }
            className="rounded-full border border-[var(--border)] px-3 py-1 text-[var(--muted)]
                       hover:border-[var(--accent-dim)] hover:text-[var(--ink)] transition-colors"
          >
            European Private Debt Brief
          </button>
        </div>

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
          <label className="flex items-center gap-2 cursor-pointer text-[var(--ink)]">
            <input
              type="radio"
              name="mode"
              value="deep"
              checked={mode === "deep"}
              onChange={() => setMode("deep")}
              className="accent-[var(--accent)]"
            />
            <span>Deep research</span>
          </label>
        </div>

        <div className="text-center pt-2 space-y-3">
          <button
            type="submit"
            disabled={loading || !topic.trim()}
            className="rounded-lg bg-[var(--accent)] px-10 py-3 font-semibold text-[#1a1408]
                       hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all"
          >
            {loading
              ? "Researching…"
              : mode === "deep"
                ? "Start deep research"
                : "Start research"}
          </button>
          <p className="text-sm text-[var(--muted)]">
            <Link href="/plan" className="text-[var(--link)] hover:underline">
              Deep planning wizard
            </Link>
            {" "}— clarify scope before executing
          </p>
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

    </main>
  );
}
