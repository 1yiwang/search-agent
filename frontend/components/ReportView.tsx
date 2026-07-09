"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Citation, ResearchReport, StructuredFinding } from "@/lib/api";
import { CitationPanel } from "@/components/CitationPanel";
import { countUniqueDomains, normalizeUrl } from "@/lib/normalizeUrl";
import { snapshotForUrl } from "@/lib/sourcePreview";

type SortKey = "confidence" | "date" | "entity";
type SortDir = "asc" | "desc";

const CONF_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

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

function FindingsTable({
  rows,
  onCitationClick,
  compact,
}: {
  rows: StructuredFinding[];
  onCitationClick: (index: number) => void;
  compact?: boolean;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("confidence");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "confidence") {
        cmp = (CONF_RANK[a.confidence] ?? 0) - (CONF_RANK[b.confidence] ?? 0);
      } else if (sortKey === "date") {
        cmp = a.date.localeCompare(b.date);
      } else {
        cmp = a.entity.localeCompare(b.entity);
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
    <div className={`overflow-x-auto rounded-lg border border-[var(--border)]${compact ? " findings-table" : ""}`}>
      <table className={`w-full ${compact ? "text-[13px] tabular-nums" : "text-sm"}`}>
        <thead className="bg-[var(--surface)] border-b border-[var(--border)]">
          <tr>
            <th className={thClass} onClick={() => toggleSort("entity")}>
              Entity {sortKey === "entity" ? (sortDir === "asc" ? "↑" : "↓") : ""}
            </th>
            <th className={thClass}>Signal</th>
            <th className={thClass} onClick={() => toggleSort("date")}>
              Date {sortKey === "date" ? (sortDir === "asc" ? "↑" : "↓") : ""}
            </th>
            <th className={thClass} onClick={() => toggleSort("confidence")}>
              Confidence {sortKey === "confidence" ? (sortDir === "asc" ? "↑" : "↓") : ""}
            </th>
            <th className="text-left text-xs uppercase tracking-wider text-[var(--muted)] py-3 px-3">
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
              <td className="py-3 px-3 font-medium text-[var(--ink)] align-top max-w-[10rem]">
                {row.entity || "—"}
              </td>
              <td className="py-3 px-3 text-[var(--ink)]/90 align-top leading-relaxed">
                {row.signal}
              </td>
              <td className="py-3 px-3 text-[var(--muted)] align-top whitespace-nowrap">
                {row.date || "—"}
              </td>
              <td className="py-3 px-3 align-top">{confidenceBadge(row.confidence)}</td>
              <td className="py-3 px-3 align-top">
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
    <div className="space-y-6">
      {groups.map(
        (g) =>
          g.items.length > 0 && (
            <div key={g.label}>
              <h3 className="text-xs uppercase tracking-widest text-[var(--muted)] mb-3">
                {g.label}
              </h3>
              <ul className="space-y-3">
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
          entity: f.source_title.slice(0, 48),
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
    <main className="min-h-screen">
      {/* Masthead */}
      <header className="border-b border-[var(--border)] bg-[var(--surface)]/60 backdrop-blur-sm sticky top-0 z-20">
        <div className="mx-auto max-w-6xl px-4 py-4 flex flex-wrap items-center justify-between gap-3">
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

      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-col lg:flex-row gap-10">
          <article
            className={`flex-1 min-w-0 space-y-10${isInvestorBrief ? " investor-brief" : ""}`}
          >
            {/* Hero */}
            <div className="relative">
              <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent-dim)] mb-3">
                {briefLabel}
              </p>
              <h1
                className={`font-display text-[var(--ink)] leading-tight max-w-3xl${
                  isInvestorBrief ? " brief-title" : " text-3xl md:text-4xl"
                }`}
              >
                {report.topic}
              </h1>
              <div
                className="mt-6 absolute -left-4 top-0 bottom-0 w-1 rounded-full bg-gradient-to-b from-[var(--accent)] to-transparent opacity-60 hidden sm:block"
                aria-hidden
              />
            </div>

            {/* Executive summary */}
            <section className="rounded-xl border border-[var(--accent)]/25 bg-gradient-to-br from-[var(--surface-raised)] to-[var(--surface)] p-6 md:p-8">
              <h2 className="text-xs uppercase tracking-widest text-[var(--accent)] mb-4">
                Executive Summary
              </h2>
              <p
                className={`text-[var(--ink)] leading-relaxed${
                  isInvestorBrief ? " brief-summary" : " text-lg font-display"
                }`}
              >
                {summary}
              </p>
            </section>

            {/* Structured table */}
            {tableRows.length > 0 && (
              <section>
                <h2
                  className={`font-display text-[var(--ink)] mb-4${
                    isInvestorBrief ? " brief-section-title" : " text-xl"
                  }`}
                >
                  {tableHeading}
                </h2>
                <FindingsTable
                  rows={tableRows}
                  onCitationClick={openCitation}
                  compact={isInvestorBrief}
                />
              </section>
            )}

            {/* Investor brief sections */}
            {isInvestorBrief && report.fund_activity && (
              <section className="rounded-lg border border-[var(--border)] p-5 bg-[var(--surface)]">
                <h2
                  className={`font-display text-[var(--ink)] mb-3${
                    isInvestorBrief ? " brief-section-title" : " text-xl"
                  }`}
                >
                  Fund & Product Activity
                </h2>
                <p
                  className={`text-[var(--ink)]/85 leading-relaxed whitespace-pre-wrap${
                    isInvestorBrief ? " brief-body" : " text-sm"
                  }`}
                >
                  {report.fund_activity}
                </p>
              </section>
            )}
            {isInvestorBrief && report.credit_risk_watch && (
              <section className="rounded-lg border border-[var(--border)] p-5 bg-[var(--surface)]">
                <h2
                  className={`font-display text-[var(--ink)] mb-3${
                    isInvestorBrief ? " brief-section-title" : " text-xl"
                  }`}
                >
                  Credit Risk Watch
                </h2>
                <p
                  className={`text-[var(--ink)]/85 leading-relaxed whitespace-pre-wrap${
                    isInvestorBrief ? " brief-body" : " text-sm"
                  }`}
                >
                  {report.credit_risk_watch}
                </p>
              </section>
            )}

            {/* Key findings */}
            <section>
              <h2
                className={`font-display text-[var(--ink)] mb-4${
                  isInvestorBrief ? " brief-section-title" : " text-xl"
                }`}
              >
                Key Findings
              </h2>
              <KeyFindingsList facts={report.facts} onCitationClick={openCitation} />
            </section>

            {/* Coverage */}
            {(report.coverage || report.gaps) && (
              <section className="grid md:grid-cols-2 gap-4">
                {report.coverage && (
                  <div className="rounded-lg border border-[var(--border)] p-5 bg-[var(--surface)]">
                    <h3 className="text-xs uppercase tracking-widest text-[var(--muted)] mb-2">
                      Coverage
                    </h3>
                    <p className="text-sm text-[var(--ink)]/85 leading-relaxed">
                      {report.coverage}
                    </p>
                  </div>
                )}
                {report.gaps && (
                  <div className="rounded-lg border border-[var(--border)] p-5 bg-[var(--surface)]">
                    <h3 className="text-xs uppercase tracking-widest text-[var(--muted)] mb-2">
                      Gaps
                    </h3>
                    <p className="text-sm text-[var(--ink)]/85 leading-relaxed">
                      {report.gaps}
                    </p>
                  </div>
                )}
              </section>
            )}

            {/* Sources */}
            <section className="border-t border-[var(--border)] pt-8">
              <h2
                className={`font-display text-[var(--ink)] mb-4${
                  isInvestorBrief ? " brief-section-title" : " text-xl"
                }`}
              >
                Sources
              </h2>
              <ol className={`space-y-4${isInvestorBrief ? " brief-body" : " text-sm"}`}>
                {groupedSources.map((src) => (
                  <li key={normalizeUrl(src.url)} className="flex gap-2">
                    <span className="citation-mark font-semibold shrink-0 text-xs">
                      {src.indices.map((i) => `[${i}]`).join(" ")}
                    </span>
                    <div>
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
                      <p className="text-[var(--muted)] mt-1 italic leading-relaxed text-sm">
                        &ldquo;{src.quote.slice(0, 200)}
                        {src.quote.length > 200 ? "…" : ""}&rdquo;
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </article>

          {/* Citation panel */}
          <aside className="lg:w-[28rem] shrink-0">
            <div className="lg:sticky lg:top-24">
              {activeCitation ? (
                <CitationPanel
                  citation={activeCitation}
                  snapshot={snapshotForUrl(
                    report.source_snapshots,
                    activeCitation.source_url
                  )}
                  onClose={onCitationClose}
                />
              ) : (
                <p className="text-xs text-[var(--muted)] border border-dashed border-[var(--border)] rounded-lg p-4 text-center">
                  点击 [{` `}n{` `}] 引用，在右侧预览原文并高亮对应片段
                </p>
              )}
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
