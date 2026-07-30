"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listReports, type ReportSummary } from "@/lib/api";
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

  useEffect(() => {
    listReports(50)
      .then(setReports)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
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
          Reports are stored on your personal API — bookmark a report URL or find it here.
        </p>
        <div className="mt-4">
          <ApiStatus />
        </div>
      </header>

      {loading && (
        <p className="text-sm text-[var(--muted)]">Loading…</p>
      )}

      {error && (
        <p className="text-sm text-red-600">
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
    </main>
  );
}
