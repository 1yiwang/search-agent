"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  streamResearch,
  checkApiHealth,
  type SSEEvent,
} from "@/lib/api";
import { formatProgressEvent } from "@/lib/formatProgress";
import { getApiToken } from "@/lib/auth";
import { loadSettings } from "@/lib/settings";
import { useSettingsUi } from "@/lib/settingsUi";
import { researchReportPath, slugFromReportReady } from "@/lib/researchNav";

type Mode = "quick" | "deep";
type Depth = "fast" | "standard" | "deep";

export default function SearchPage() {
  const router = useRouter();
  const { openSettings } = useSettingsUi();
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<Mode>("quick");
  const [depth, setDepth] = useState<Depth>("deep");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [hasKey, setHasKey] = useState(true);

  useEffect(() => {
    function refresh() {
      setHasKey(Boolean(loadSettings().llmApiKey.trim()));
    }
    refresh();
    window.addEventListener("search-agent-settings-saved", refresh);
    return () => window.removeEventListener("search-agent-settings-saved", refresh);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || loading) return;

    if (mode === "quick" && depth !== "fast") {
      const q = new URLSearchParams({
        topic: topic.trim(),
        depth,
      });
      router.push(`/brief?${q.toString()}`);
      return;
    }
    if (mode === "deep") {
      const q = new URLSearchParams({
        topic: topic.trim(),
        depth: "deep",
      });
      router.push(`/brief?${q.toString()}`);
      return;
    }

    setLoading(true);
    setProgress([]);

    const health = await checkApiHealth();
    if (!health.ok) {
      setProgress(["Error: API offline — start backend on :8000 first."]);
      setLoading(false);
      return;
    }
    if (health.apiAuthRequired && !getApiToken()) {
      setProgress([
        "Error: API requires login — open /login, enter site password, then retry.",
      ]);
      setLoading(false);
      return;
    }
    if (!loadSettings().llmApiKey.trim()) {
      setProgress(["Error: Add your LLM API key in Settings before researching."]);
      openSettings();
      setLoading(false);
      return;
    }

    const events: SSEEvent[] = [];
    try {
      const stream = streamResearch({ topic: topic.trim(), depth: "fast" });

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
        <h1 className="font-display brand-title text-4xl md:text-5xl text-[var(--ink)]">
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
                     focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
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
            <span>Multi-section deep</span>
          </label>
        </div>

        {mode === "quick" && (
          <div className="flex flex-wrap items-center justify-center gap-4 text-sm">
            {(
              [
                ["fast", "Fast", "8 sources"],
                ["standard", "Standard", "15 sources"],
                ["deep", "Deep", "20 sources"],
              ] as const
            ).map(([value, label, hint]) => (
              <label
                key={value}
                className="flex items-center gap-2 cursor-pointer text-[var(--ink)]"
                title={hint}
              >
                <input
                  type="radio"
                  name="depth"
                  value={value}
                  checked={depth === value}
                  onChange={() => setDepth(value)}
                  className="accent-[var(--accent)]"
                />
                <span>
                  {label}
                  <span className="ml-1 text-[var(--muted)]">({hint})</span>
                </span>
              </label>
            ))}
          </div>
        )}

        <div className="text-center pt-2 space-y-3">
          <button
            type="submit"
            disabled={loading || !topic.trim()}
            className="rounded-lg bg-[var(--accent)] px-10 py-3 font-semibold text-[var(--cta-ink)]
                       hover:brightness-[0.97] disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all"
          >
            {loading
              ? "Researching…"
              : mode === "deep" || (mode === "quick" && depth !== "fast")
                ? "Continue to brief →"
                : "Start fast research"}
          </button>
          {!hasKey && (
            <p className="text-sm text-[var(--muted)]">
              <button
                type="button"
                onClick={() => {
                  openSettings();
                }}
                className="text-[var(--ink)] underline-offset-2 hover:underline"
              >
                Add API key
              </button>{" "}
              before researching.
            </p>
          )}
          <p className="text-xs text-[var(--muted)]">
            <Link href="/plan" className="hover:text-[var(--ink)]">
              Legacy multi-section plan
            </Link>
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
