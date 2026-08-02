"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getReport, type ResearchReport, type Citation } from "@/lib/api";
import { cacheReport, getCachedReport, isApiOfflineError } from "@/lib/reportCache";
import { ReportView } from "@/components/ReportView";

export default function ReportPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [report, setReport] = useState<ResearchReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setFromCache(false);
    getReport(slug)
      .then((r) => {
        cacheReport(r);
        setReport(r);
        setFromCache(false);
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : "Failed to load";
        const cached = getCachedReport(slug);
        if (cached) {
          setReport(cached);
          setFromCache(true);
          setError(
            isApiOfflineError(message)
              ? "API offline — showing a copy cached in this browser."
              : `${message} — showing browser cache.`,
          );
        } else {
          setReport(null);
          setError(
            isApiOfflineError(message)
              ? `${message} If you opened this report before on this device, it would appear from cache.`
              : message,
          );
        }
      })
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-24 text-center text-[var(--muted)]">
        <p className="text-sm uppercase tracking-widest animate-pulse">
          Loading brief…
        </p>
      </main>
    );
  }

  if (error && !report) {
    return (
      <main className="mx-auto max-w-md px-4 py-24 text-center">
        <p className="text-red-400 mb-4">{error}</p>
        <a href="/history" className="text-sm text-[var(--link)] hover:underline">
          Back to saved reports
        </a>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="mx-auto max-w-md px-4 py-24 text-center">
        <p className="text-red-400 mb-4">Report not found.</p>
        <a href="/history" className="text-sm text-[var(--link)] hover:underline">
          Back to saved reports
        </a>
      </main>
    );
  }

  return (
    <>
      {fromCache && error ? (
        <div className="border-b border-amber-700/30 bg-amber-50/10 px-4 py-2 text-center text-xs text-amber-800 dark:text-amber-200/90">
          {error}
        </div>
      ) : null}
      <ReportView
        report={report}
        activeCitation={activeCitation}
        onCitationSelect={setActiveCitation}
        onCitationClose={() => setActiveCitation(null)}
      />
    </>
  );
}
