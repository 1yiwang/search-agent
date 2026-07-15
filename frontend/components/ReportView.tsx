"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Citation, ResearchReport, StructuredFinding } from "@/lib/api";
import { CitationModal } from "@/components/CitationModal";
import { countUniqueDomains, normalizeUrl } from "@/lib/normalizeUrl";
import { snapshotForUrl } from "@/lib/sourcePreview";

type SortKey = "confidence" | "date" | "signal";
type SortDir = "asc" | "desc";

const CONF_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

/** Editorial column: wide enough for tables, with side gutters. */
const PAGE_GUTTER = "mx-auto w-full max-w-5xl px-5 sm:px-8 lg:px-10";

function confidenceBadge(conf: string) {
  const styles: Record<string, string> = {
    high: "bg-[var(--verify)]/15 text-[var(--verify)] border-[var(--verify)]/30",
    medium: "bg-[var(--accent)]/10 text-[var(--accent)] border-[var(--accent)]/30",
    low: "bg-[var(--muted)]/10 text-[var(--muted)] border-[var(--border)]",
  };
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium border ${
        styles[conf] ?? styles.medium
      }`}
    >
      {conf}
    </span>
  );
}

function signalTypeBadge(signalType?: string) {
  const label = (signalType || "other").replace(/_/g, " ");
  if (!signalType || signalType === "other") {
    return <span className="text-[var(--muted)] text-xs">{label}</span>;
  }
  return (
    <span className="inline-block rounded px-2 py-0.5 text-[10px] font-medium border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)]/80 uppercase tracking-wide">
      {label}
    </span>
  );
}

function FindingsTable({
  rows,
  onCitationClick,
}: {
  rows: StructuredFinding[];
  onCitationClick: (index: number) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("confidence");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const showType = rows.some((r) => r.signal_type && r.signal_type !== "other");

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "confidence") {
        cmp = (CONF_RANK[a.confidence] ?? 0) - (CONF_RANK[b.confidence] ?? 0);
      } else if (sortKey === "date") {
        cmp = a.date.localeCompare(b.date);
      } else {
        cmp = a.signal.localeCompare(b.signal);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "confidence" ? "desc" : "asc");
    }
  }

  const thClass =
    "text-left text-xs uppercase tracking-wider text-[var(--muted)] py-3 px-3 cursor-pointer hover:text-[var(--ink)] select-none";

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)] findings-table bg-[var(--surface)]/40">
      <table className="w-full text-sm tabular-nums">
        <thead className="bg-[var(--surface)] border-b border-[var(--border)]">
          <tr>
            <th className={thClass} onClick={() => toggleSort("signal")}>
              Signal {sortKey === "signal" ? (sortDir === "asc" ? "↑" : "↓") : ""}
            </th>
            {showType && (
              <th className="text-left text-xs uppercase tracking-wider text-[var(--muted)] py-3 px-3 w-28">
                Type
              </th>
            )}
            <th className={`${thClass} w-28`} onClick={() => toggleSort("date")}>
              Date {sortKey === "date" ? (sortDir === "asc" ? "↑" : "↓") : ""}
            </th>
            <th className={`${thClass} w-32`} onClick={() => toggleSort("confidence")}>
              Confidence {sortKey === "confidence" ? (sortDir === "asc" ? "↑" : "↓") : ""}
            </th>
            <th className="text-left text-xs uppercase tracking-wider text-[var(--muted)] py-3 px-3 w-16">
              Ref
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={`${row.citation_index}-${i}`}
              className="border-b border-[var(--border)]/60 hover:bg-[var(--surface)]/80"
            >
              <td className="py-3.5 px-3 text-[var(--ink)]/90 align-top leading-relaxed">
                {row.signal}
              </td>
              {showType && (
                <td className="py-3.5 px-3 align-top">{signalTypeBadge(row.signal_type)}</td>
              )}
              <td className="py-3.5 px-3 text-[var(--muted)] align-top whitespace-nowrap">
                {row.date || "—"}
              </td>
              <td className="py-3.5 px-3 align-top">{confidenceBadge(row.confidence)}</td>
              <td className="py-3.5 px-3 align-top">
                {row.citation_index > 0 ? (
                  <button
                    type="button"
                    onClick={() => onCitationClick(row.citation_index)}
                    className="citation-mark text-sm hover:underline"
                  >
                    [{row.citation_index}]
                  </button>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KeyFindingsList({
  facts,
  onCitationClick,
}: {
  facts: ResearchReport["facts"];
  onCitationClick: (index: number) => void;
}) {
  const groups = [
    { label: "High confidence", items: facts.filter((f) => f.confidence === "high") },
    { label: "Medium confidence", items: facts.filter((f) => f.confidence === "medium") },
    { label: "Low confidence", items: facts.filter((f) => f.confidence === "low") },
  ];

  return (
    <div className="space-y-8">
      {groups.map(
        (g) =>
          g.items.length > 0 && (
            <div key={g.label}>
              <h3 className="text-xs uppercase tracking-widest text-[var(--muted)] mb-3">
                {g.label}
              </h3>
              <ul className="space-y-4">
                {g.items.map((fact, i) => {
                  const idx =
                    facts.findIndex(
                      (f) =>
                        f.fact === fact.fact && f.source_url === fact.source_url
                    ) + 1;
                  return (
                    <li
                      key={`${fact.source_url}-${i}`}
                      className="border-l-2 border-[var(--border)] pl-4 text-[var(--ink)]/90 leading-relaxed"
                    >
                      {fact.fact}{" "}
                      <button
                        type="button"
                        onClick={() => onCitationClick(idx)}
                        className="citation-mark hover:underline"
                      >
                        [{idx}]
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )
      )}
    </div>
  );
}

function Section({
  label,
  title,
  children,
  className = "",
}: {
  label?: string;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`report-section ${className}`}>
      {label ? <span className="report-section-label">{label}</span> : null}
      <h2 className="font-display brief-section-title text-[var(--ink)] mb-5">{title}</h2>
      {children}
    </section>
  );
}

export function ReportView({
  report,
  activeCitation,
  onCitationSelect,
  onCitationClose,
}: {
  report: ResearchReport;
  activeCitation: Citation | null;
  onCitationSelect: (c: Citation) => void;
  onCitationClose: () => void;
}) {
  const summary =
    report.summary ||
    report.facts.slice(0, 2).map((f) => f.fact).join(" ") ||
    "No summary available for this report.";

  const isInvestorBrief = report.report_type === "investor_brief";
  const briefLabel = isInvestorBrief ? "Investor Brief" : "Intelligence Brief";
  const tableHeading = isInvestorBrief ? "Market Signals" : "Structured Findings";

  const uniqueSourceCount = useMemo(
    () => countUniqueDomains(report.facts.map((f) => f.source_url)),
    [report.facts]
  );

  const groupedSources = useMemo(() => {
    const byUrl = new Map<
      string,
      { name: string; url: string; indices: number[]; quote: string }
    >();
    for (const c of report.citations) {
      const key = normalizeUrl(c.source_url);
      const existing = byUrl.get(key);
      if (existing) {
        existing.indices.push(c.index);
      } else {
        byUrl.set(key, {
          name: c.source_name,
          url: c.source_url,
          indices: [c.index],
          quote: c.quoted_text,
        });
      }
    }
    return Array.from(byUrl.values());
  }, [report.citations]);

  const displaySourceCount =
    uniqueSourceCount || report.metadata?.source_count || groupedSources.length;

  const tableRows: StructuredFinding[] =
    report.structured_findings && report.structured_findings.length > 0
      ? report.structured_findings
      : report.facts.map((f, i) => ({
          entity: "",
          signal: f.fact,
          date: "",
          confidence: f.confidence,
          citation_index: i + 1,
        }));

  function openCitation(index: number) {
    const c = report.citations.find((x) => x.index === index);
    if (c) onCitationSelect(c);
  }

  return (
    <main className="min-h-screen report-doc">
      <header className="border-b border-[var(--border)] bg-[var(--surface)]/60 backdrop-blur-sm sticky top-0 z-20">
        <div className={`${PAGE_GUTTER} py-3 flex flex-wrap items-center justify-between gap-3`}>
          <nav className="flex items-center gap-4 text-sm text-[var(--muted)]">
            <Link href="/" className="hover:text-[var(--ink)]">
              New search
            </Link>
            <span className="text-[var(--border)]">|</span>
            <Link href="/history" className="hover:text-[var(--ink)]">
              Saved reports
            </Link>
          </nav>
          {report.metadata && (
            <p className="text-xs text-[var(--muted)] tabular-nums">
              {report.metadata.execution_time_seconds.toFixed(0)}s ·{" "}
              {displaySourceCount} sources · {report.facts.length} facts
            </p>
          )}
        </div>
      </header>

      <div className={`${PAGE_GUTTER} py-12 sm:py-14`}>
        {/* Document masthead */}
        <header className="mb-2">
          <p className="text-xs uppercase tracking-[0.22em] text-[var(--accent-dim)] mb-3">
            {briefLabel}
          </p>
          <h1 className="font-display brief-title text-[var(--ink)]">{report.topic}</h1>
          {report.metadata && (
            <div className="report-meta-strip tabular-nums">
              {report.metadata.completed_at ? (
                <span>
                  {new Date(report.metadata.completed_at).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </span>
              ) : null}
              <span>{displaySourceCount} sources</span>
              <span>{report.facts.length} facts</span>
              <span>{report.metadata.execution_time_seconds.toFixed(0)}s</span>
            </div>
          )}
        </header>

        <article className="mt-10">
          <section className="report-section">
            <span className="report-section-label">Overview</span>
            <h2 className="font-display brief-section-title text-[var(--ink)] mb-5">
              Executive Summary
            </h2>
            <div className="report-lead">
              <p className="brief-summary text-[var(--ink)]">{summary}</p>
            </div>
          </section>

          {tableRows.length > 0 && (
            <Section label="Signals" title={tableHeading}>
              <FindingsTable rows={tableRows} onCitationClick={openCitation} />
            </Section>
          )}

          {isInvestorBrief && report.fund_activity && (
            <Section label="Products" title="Fund & Product Activity">
              <p className="brief-body text-[var(--ink)]/90 whitespace-pre-wrap">
                {report.fund_activity}
              </p>
            </Section>
          )}

          {isInvestorBrief && report.credit_risk_watch && (
            <Section label="Risk" title="Credit Risk Watch">
              <p className="brief-body text-[var(--ink)]/90 whitespace-pre-wrap">
                {report.credit_risk_watch}
              </p>
            </Section>
          )}

          <Section label="Evidence" title="Key Findings">
            <KeyFindingsList facts={report.facts} onCitationClick={openCitation} />
          </Section>

          {(report.coverage || report.gaps) && (
            <Section label="Scope" title="Coverage & Gaps">
              <div className="grid sm:grid-cols-2 gap-8">
                {report.coverage && (
                  <div>
                    <h3 className="text-xs uppercase tracking-widest text-[var(--muted)] mb-3">
                      Coverage
                    </h3>
                    <p className="brief-body text-[var(--ink)]/85">{report.coverage}</p>
                  </div>
                )}
                {report.gaps && (
                  <div>
                    <h3 className="text-xs uppercase tracking-widest text-[var(--muted)] mb-3">
                      Gaps
                    </h3>
                    <p className="brief-body text-[var(--ink)]/85">{report.gaps}</p>
                  </div>
                )}
              </div>
            </Section>
          )}

          <Section label="Sources" title="Sources" className="pb-8">
            <ol className="space-y-5 brief-body">
              {groupedSources.map((src) => (
                <li key={normalizeUrl(src.url)} className="flex gap-3">
                  <span className="citation-mark font-semibold shrink-0 text-xs pt-0.5">
                    {src.indices.map((i) => `[${i}]`).join(" ")}
                  </span>
                  <div className="min-w-0">
                    <button
                      type="button"
                      onClick={() => openCitation(src.indices[0])}
                      className="text-[var(--link)] hover:underline text-left"
                    >
                      {src.name}
                    </button>
                    <p className="text-xs text-[var(--muted)] mt-0.5">
                      {src.indices.length} fact{src.indices.length > 1 ? "s" : ""} from this
                      source
                    </p>
                    <p className="text-[var(--muted)] mt-1.5 italic leading-relaxed text-sm">
                      &ldquo;{src.quote.slice(0, 200)}
                      {src.quote.length > 200 ? "…" : ""}&rdquo;
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </Section>
        </article>
      </div>

      {activeCitation && (
        <CitationModal
          citation={activeCitation}
          snapshot={snapshotForUrl(
            report.source_snapshots,
            activeCitation.source_url
          )}
          onClose={onCitationClose}
        />
      )}
    </main>
  );
}
