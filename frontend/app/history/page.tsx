"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listReports, type ReportSummary } from "@/lib/api";
import {
  isApiOfflineError,
  listCachedReports,
} from "@/lib/reportCache";
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

export default function HistoryPage() {
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
              ? "Personal API offline — showing reports previously opened in this browser. Start API to sync the full list."
              : `${message} — showing browser cache.`,
          );
        } else {
          setReports([]);
          setFromCache(false);
          setError(
            isApiOfflineError(message)
              ? "Personal API offline. Saved reports live on your PC — run .\\scripts\\start-personal.ps1, then refresh. Or open a report URL you bookmarked after viewing it once (it will cache here)."
              : message,
          );
        }
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-16 md:py-24">
      <header className="mb-10">
        <Link href="/" className="text-sm text-[var(--muted)] hover:text-[var(--ink)]">
          ← New search
        </Link>
        {" · "}
        <Link href="/watchlist" className="text-sm text-[var(--link)] hover:underline">
          Watchlist
        </Link>
        <h1 className="font-display text-4xl text-[var(--ink)] mt-4">Saved reports</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Full list needs your personal API. Reports you have opened before are also cached in this
          browser for offline reading.
        </p>
        <div className="mt-4">
          <ApiStatus />
        </div>
      </header>

      {loading && (
        <p className="text-sm text-[var(--muted)]">Loading…</p>
      )}

      {error && (
        <p className="mb-6 text-sm text-amber-800 dark:text-amber-200/90 rounded-lg border border-amber-700/30 bg-amber-50/10 px-4 py-3">
          {error}
          {error.includes("Not signed in") && (
            <>
              {" "}
              <Link href="/login?next=/history" className="text-[var(--link)] hover:underline">
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

      {!loading && error && reports.length === 0 && (
        <p className="text-sm text-[var(--muted)]">
          Tip: after you open a report once while the API is online, it stays readable here offline.
        </p>
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
    </main>
  );
}
