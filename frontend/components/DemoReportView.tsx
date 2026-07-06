"use client";

import { useState } from "react";
import type { Citation, ResearchReport } from "@/lib/api";
import { ReportView } from "@/components/ReportView";

export function DemoReportView({ report }: { report: ResearchReport }) {
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  return (
    <>
      <div className="mx-auto max-w-6xl px-4 pt-4">
        <p className="text-xs text-[var(--muted)] border border-dashed border-[var(--border)] rounded-lg px-4 py-2 text-center">
          Static demo — no API or keys required. Citations are illustrative from a real research run.
        </p>
      </div>
      <ReportView
        report={report}
        activeCitation={activeCitation}
        onCitationSelect={setActiveCitation}
        onCitationClose={() => setActiveCitation(null)}
      />
    </>
  );
}
