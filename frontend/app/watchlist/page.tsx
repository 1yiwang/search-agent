"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  checkApiHealth,
  createWatch,
  deleteWatch,
  getLatestWatchDelta,
  listWatches,
  streamWatchRun,
  type SSEEvent,
  type WatchDelta,
  type WatchItem,
} from "@/lib/api";
import { formatProgressEvent } from "@/lib/formatProgress";
import { getApiToken } from "@/lib/auth";
import { loadSettings } from "@/lib/settings";
import { researchReportPath } from "@/lib/researchNav";
import { ApiStatus } from "@/components/ApiStatus";

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function WatchlistPage() {
  const [watches, setWatches] = useState<WatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [topic, setTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [delta, setDelta] = useState<WatchDelta | null>(null);

  const refresh = useCallback(async () => {
    const items = await listWatches();
    setWatches(items);
    return items;
  }, []);

  useEffect(() => {
    refresh()
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) {
      setDelta(null);
      return;
    }
    getLatestWatchDelta(selectedId)
      .then(setDelta)
      .catch(() => setDelta(null));
  }, [selectedId]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || creating) return;
    setCreating(true);
    setError(null);
    try {
      const item = await createWatch({
        topic: topic.trim(),
        max_sources: 10,
        cadence: "manual",
        recency_days: 14,
      });
      setTopic("");
      await refresh();
      setSelectedId(item.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  async function handleRun(watch: WatchItem) {
    if (runningId) return;
    setRunningId(watch.id);
    setSelectedId(watch.id);
    setProgress([]);
    setError(null);

    const health = await checkApiHealth();
    if (!health.ok) {
      setProgress(["Error: API offline — start backend on :8000 first."]);
      setRunningId(null);
      return;
    }
    if (health.apiAuthRequired && !getApiToken()) {
      setProgress(["Error: API requires login — open /login first."]);
      setRunningId(null);
      return;
    }
    if (!loadSettings().llmApiKey.trim()) {
      setProgress(["Error: Add your LLM API key in Settings first."]);
      setRunningId(null);
      return;
    }

    try {
      const events: SSEEvent[] = [];
      for await (const event of streamWatchRun(watch.id)) {
        events.push(event);
        setProgress((prev) => [...prev, formatProgressEvent(event)]);
      }
      await refresh();
      const latest = await getLatestWatchDelta(watch.id);
      setDelta(latest);
    } catch (err) {
      setProgress((prev) => [
        ...prev,
        `Error: ${err instanceof Error ? err.message : "Run failed"}`,
      ]);
    } finally {
      setRunningId(null);
    }
  }

  async function handleDelete(watchId: string) {
    if (!confirm("Remove this watch?")) return;
    await deleteWatch(watchId);
    if (selectedId === watchId) {
      setSelectedId(null);
      setDelta(null);
    }
    await refresh();
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-16 md:py-24">
      <header className="mb-10">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href="/" className="text-[var(--muted)] hover:text-[var(--ink)]">
            ← New search
          </Link>
          <Link href="/history" className="text-[var(--link)] hover:underline">
            Saved reports
          </Link>
        </div>
        <h1 className="font-display text-4xl text-[var(--ink)] mt-4">Watchlist</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Subscribe to a topic, re-run research, and compare what changed since last time.
        </p>
        <div className="mt-4">
          <ApiStatus />
        </div>
      </header>

      <form onSubmit={handleCreate} className="mb-10 space-y-3">
        <label className="block text-sm text-[var(--muted)]" htmlFor="watch-topic">
          Topic to watch
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id="watch-topic"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="European corporate direct lending trends"
            className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-[var(--ink)] outline-none focus:border-[var(--accent-dim)]"
            minLength={3}
            required
          />
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-[var(--ink)] px-5 py-3 text-sm text-[var(--paper)] disabled:opacity-50"
          >
            {creating ? "Adding…" : "Add watch"}
          </button>
        </div>
      </form>

      {loading && <p className="text-sm text-[var(--muted)]">Loading…</p>}
      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {!loading && watches.length === 0 && (
        <p className="text-sm text-[var(--muted)]">No watches yet. Add a topic above.</p>
      )}

      <ul className="space-y-3 mb-10">
        {watches.map((w) => (
          <li
            key={w.id}
            className={`rounded-lg border px-5 py-4 transition-colors ${
              selectedId === w.id
                ? "border-[var(--accent-dim)] bg-[var(--surface)]"
                : "border-[var(--border)] bg-[var(--surface)]"
            }`}
          >
            <button
              type="button"
              className="w-full text-left"
              onClick={() => setSelectedId(w.id)}
            >
              <div className="font-medium text-[var(--ink)] line-clamp-2">{w.topic}</div>
              <div className="mt-1 text-xs text-[var(--muted)]">
                {w.cadence} · {w.recency_days}d window
                {w.last_run_at ? ` · last run ${formatDate(w.last_run_at)}` : " · never run"}
                {!w.enabled ? " · disabled" : ""}
              </div>
            </button>
            <div className="mt-3 flex flex-wrap gap-3 text-sm">
              <button
                type="button"
                onClick={() => handleRun(w)}
                disabled={runningId === w.id}
                className="text-[var(--link)] hover:underline disabled:opacity-50"
              >
                {runningId === w.id ? "Running…" : "Run now"}
              </button>
              {w.latest_slug && (
                <Link
                  href={researchReportPath(w.latest_slug)}
                  className="text-[var(--link)] hover:underline"
                >
                  Latest report
                </Link>
              )}
              <button
                type="button"
                onClick={() => handleDelete(w.id)}
                className="text-[var(--muted)] hover:text-red-600"
              >
                Remove
              </button>
            </div>
          </li>
        ))}
      </ul>

      {progress.length > 0 && (
        <section className="mb-10">
          <h2 className="text-sm font-medium text-[var(--ink)] mb-2">Run progress</h2>
          <ul className="max-h-48 overflow-y-auto space-y-1 text-xs text-[var(--muted)] font-mono">
            {progress.map((line, i) => (
              <li key={`${i}-${line.slice(0, 24)}`}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      {delta && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-5">
          <h2 className="font-display text-2xl text-[var(--ink)]">Latest delta</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            +{delta.added.length} added · −{delta.removed.length} removed · ~
            {delta.changed.length} changed · {delta.unchanged_count} unchanged
          </p>
          {delta.curr_slug && (
            <Link
              href={researchReportPath(delta.curr_slug)}
              className="mt-2 inline-block text-sm text-[var(--link)] hover:underline"
            >
              Open current report →
            </Link>
          )}
          {delta.added.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-medium text-[var(--ink)]">Added</h3>
              <ul className="mt-2 space-y-2 text-sm text-[var(--ink)]/90">
                {delta.added.slice(0, 12).map((row, i) => (
                  <li key={`a-${i}`}>
                    <span className="font-medium">{row.entity || "Finding"}</span>
                    {": "}
                    {(row.signal || row.fact).slice(0, 160)}
                    {row.date ? ` (${row.date})` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {delta.removed.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-medium text-[var(--ink)]">Removed</h3>
              <ul className="mt-2 space-y-2 text-sm text-[var(--muted)]">
                {delta.removed.slice(0, 8).map((row, i) => (
                  <li key={`r-${i}`}>
                    {(row.entity ? `${row.entity}: ` : "") +
                      (row.signal || row.fact).slice(0, 140)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
