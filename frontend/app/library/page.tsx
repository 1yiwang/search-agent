"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import {
  checkApiHealth,
  createWatch,
  deleteWatch,
  getLatestWatchDelta,
  listReports,
  listWatches,
  streamWatchRun,
  type ReportSummary,
  type SSEEvent,
  type WatchDelta,
  type WatchItem,
} from "@/lib/api";
import { formatProgressEvent } from "@/lib/formatProgress";
import { getApiToken } from "@/lib/auth";
import { loadSettings } from "@/lib/settings";
import { useSettingsUi } from "@/lib/settingsUi";
import {
  isApiOfflineError,
  listCachedReports,
} from "@/lib/reportCache";
import { researchReportPath } from "@/lib/researchNav";

type Tab = "saved" | "watching";

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function LibraryInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { openSettings } = useSettingsUi();
  const tabParam = searchParams.get("tab");
  const tab: Tab = tabParam === "watching" ? "watching" : "saved";

  function setTab(next: Tab) {
    const q = next === "saved" ? "/library" : "/library?tab=watching";
    router.replace(q);
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-12 md:py-16">
      <header className="mb-8">
        <h1 className="font-display text-4xl text-[var(--ink)]">Library</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Your research assets — saved reports and watched topics.
        </p>
        <div className="mt-6 flex gap-1 border-b border-[var(--border)]">
          {(
            [
              ["saved", "Saved reports"],
              ["watching", "Watching"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-4 py-2.5 text-sm transition-colors border-b-2 -mb-px ${
                tab === id
                  ? "border-[var(--accent)] text-[var(--ink)]"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      {tab === "saved" ? <SavedTab /> : <WatchingTab openSettings={openSettings} />}
    </main>
  );
}

function SavedTab() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);

  useEffect(() => {
    listReports(50)
      .then((list) => {
        setReports(list);
        setFromCache(false);
        setError(null);
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : "Failed to load";
        const cached = listCachedReports(50);
        if (cached.length > 0) {
          setReports(cached);
          setFromCache(true);
          setError(
            isApiOfflineError(message)
              ? "Personal API offline — showing reports previously opened in this browser."
              : `${message} — showing browser cache.`,
          );
        } else {
          setReports([]);
          setFromCache(false);
          setError(
            isApiOfflineError(message)
              ? "Personal API offline. Start API to sync the full list."
              : message,
          );
        }
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section>
      <p className="mb-6 text-sm text-[var(--muted)]">
        Full list needs your personal API. Reports opened before are cached in this browser.
      </p>
      {loading && <p className="text-sm text-[var(--muted)]">Loading…</p>}
      {error && (
        <p className="mb-6 text-sm text-amber-800 dark:text-amber-200/90 rounded-lg border border-amber-700/30 bg-amber-50/10 px-4 py-3">
          {error}
          {error.includes("Not signed in") && (
            <>
              {" "}
              <Link href="/login?next=/library" className="text-[var(--link)] hover:underline">
                Log in
              </Link>
            </>
          )}
        </p>
      )}
      {fromCache && !loading && reports.length > 0 && (
        <p className="mb-4 text-xs uppercase tracking-wide text-[var(--muted)]">
          Cached in this browser
        </p>
      )}
      {!loading && !error && reports.length === 0 && (
        <p className="text-sm text-[var(--muted)]">No saved reports yet. Run a search on the home page.</p>
      )}
      <ul className="space-y-3">
        {reports.map((r) => (
          <li key={r.slug}>
            <Link
              href={researchReportPath(r.slug)}
              className="block rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-4 hover:border-[var(--accent-dim)] transition-colors"
            >
              <div className="font-medium text-[var(--ink)] line-clamp-2">{r.topic}</div>
              <div className="mt-1 text-xs text-[var(--muted)]">
                {r.fact_count} facts
                {r.completed_at ? ` · ${formatDate(r.completed_at)}` : ""}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function WatchingTab({ openSettings }: { openSettings: () => void }) {
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
      openSettings();
      setRunningId(null);
      return;
    }

    try {
      for await (const event of streamWatchRun(watch.id)) {
        setProgress((prev) => [...prev, formatProgressEvent(event as SSEEvent)]);
      }
      await refresh();
      setDelta(await getLatestWatchDelta(watch.id));
    } catch (err) {
      setProgress((prev) => [
        ...prev,
        `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
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
    <section>
      <p className="mb-6 text-sm text-[var(--muted)]">
        Subscribe to a topic, re-run research, and compare what changed since last time.
      </p>
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
            className="rounded-lg bg-[var(--ink)] px-5 py-3 text-sm text-[var(--bg)] disabled:opacity-50"
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
            <button type="button" className="w-full text-left" onClick={() => setSelectedId(w.id)}>
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
    </section>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-3xl px-4 py-16 text-sm text-[var(--muted)]">Loading…</main>}>
      <LibraryInner />
    </Suspense>
  );
}
