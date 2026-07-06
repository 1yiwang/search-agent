"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getReport, type ResearchReport, type Citation } from "@/lib/api";
import { ReportView } from "@/components/ReportView";

export default function ReportPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [report, setReport] = useState<ResearchReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getReport(slug)
      .then(setReport)
      .catch((err) => setError(err.message))
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

  if (error || !report) {
    return (
      <main className="mx-auto max-w-md px-4 py-24 text-center">
        <p className="text-red-400 mb-4">{error || "Report not found."}</p>
        <a href="/history" className="text-sm text-[var(--link)] hover:underline">
          Back to saved reports
        </a>
      </main>
    );
  }

  return (
    <ReportView
      report={report}
      activeCitation={activeCitation}
      onCitationSelect={setActiveCitation}
      onCitationClose={() => setActiveCitation(null)}
    />
  );
}
