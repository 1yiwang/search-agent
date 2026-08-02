"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type {
  Citation,
  ReportArgument,
  ResearchReport,
  StructuredFinding,
} from "@/lib/api";
import { createWatch } from "@/lib/api";
import { CitationModal } from "@/components/CitationModal";
import { countUniqueDomains, normalizeUrl } from "@/lib/normalizeUrl";
import { snapshotForUrl } from "@/lib/sourcePreview";

type SortKey = "confidence" | "date" | "signal";
type SortDir = "asc" | "desc";

const CONF_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

/** Editorial column: wide enough for tables, with side gutters. */
const PAGE_GUTTER = "mx-auto w-full max-w-5xl px-5 sm:px-8 lg:px-10";

function hasCjk(text: string): boolean {
  return /[\u4e00-\u9fff]/.test(text);
}

function firstSentence(text: string): string {
  const t = text.trim();
  if (!t) return "";
  const cjk = t.match(/^[\s\S]*?[。！？]/);
  if (cjk) return cjk[0].trim();
  const en = t.match(/^[\s\S]*?[.!?](?=\s|$)/);
  if (en) return en[0].trim();
  return t;
}

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

function ArgumentsList({
  arguments: args,
  onCitationClick,
}: {
  arguments: ReportArgument[];
  onCitationClick: (index: number) => void;
}) {
  function renderBodyWithCites(text: string) {
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const m = part.match(/^\[(\d+)\]$/);
      if (m) {
        const idx = Number(m[1]);
        return (
          <button
            key={`c-${i}-${idx}`}
            type="button"
            onClick={() => onCitationClick(idx)}
            className="citation-mark hover:underline mx-0.5"
          >
            [{idx}]
          </button>
        );
      }
      return <span key={`t-${i}`}>{part}</span>;
    });
  }

  return (
    <ol className="space-y-10 list-none">
      {args.map((arg, i) => {
        const body = (arg.body || arg.detail || "").trim();
        return (
          <li key={`${i}-${arg.claim.slice(0, 24)}`} className="flex gap-4">
            <span className="font-display text-2xl text-[var(--accent-dim)] shrink-0 w-8 text-right tabular-nums leading-none pt-1">
              {i + 1}
            </span>
            <div className="min-w-0 border-l-2 border-[var(--border)] pl-4 flex-1">
              {arg.heading ? (
                <h3 className="font-display text-xl text-[var(--ink)] mb-2">{arg.heading}</h3>
              ) : null}
              <p className="text-[var(--ink)] text-lg leading-relaxed font-medium">
                {arg.claim}{" "}
                {(arg.citation_indices || []).map((idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onCitationClick(idx)}
                    className="citation-mark hover:underline ml-0.5"
                  >
                    [{idx}]
                  </button>
                ))}
              </p>
              {body ? (
                <div className="mt-3 text-[var(--ink)]/88 leading-relaxed whitespace-pre-wrap text-[15px] md:text-base">
                  {renderBodyWithCites(body)}
                </div>
              ) : null}
              {arg.confidence ? (
                <div className="mt-3">{confidenceBadge(arg.confidence)}</div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
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
  const zh = hasCjk(report.topic) || hasCjk(report.thesis || report.summary || "");
  const labels = zh
    ? {
        conclusion: "结论",
        arguments: "分论点",
        limits: "局限",
        sources: "信源",
        ledger: "信号台账",
        coverage: "检索范围",
        overview: "结论",
        evidence: "分论点",
      }
    : {
        conclusion: "Conclusion",
        arguments: "Arguments",
        limits: "Limits",
        sources: "Sources",
        ledger: "Signal ledger",
        coverage: "Coverage",
        overview: "Conclusion",
        evidence: "Arguments",
      };

  const thesis =
    (report.thesis || "").trim() ||
    firstSentence(report.summary || "") ||
    report.facts[0]?.fact ||
    (zh ? "暂无可用结论。" : "No conclusion available.");

  const argumentsList: ReportArgument[] =
    report.arguments && report.arguments.length > 0
      ? report.arguments
      : [];

  const hasStructuredArgs = argumentsList.length > 0;
  // Legacy fallback: show summary body under thesis when no arguments
  const legacySummary =
    !hasStructuredArgs && report.summary && report.summary.trim() !== thesis
      ? report.summary.trim()
      : "";

  const isInvestorBrief = report.report_type === "investor_brief";
  const briefLabel = isInvestorBrief
    ? zh
      ? "投资简报"
      : "Investor Brief"
    : zh
      ? "情报简报"
      : "Intelligence Brief";

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
      : [];

  const showLedger = tableRows.length > 0;

  function openCitation(index: number) {
    const c = report.citations.find((x) => x.index === index);
    if (c) onCitationSelect(c);
  }

  const [watchMsg, setWatchMsg] = useState<string | null>(null);
  const [watching, setWatching] = useState(false);

  async function handleWatchTopic() {
    if (watching) return;
    setWatching(true);
    setWatchMsg(null);
    try {
      const item = await createWatch({
        topic: report.topic,
        max_sources: 10,
        cadence: "manual",
        recency_days: 14,
        baseline_slug: report.slug,
      });
      setWatchMsg(`Watching — open /watchlist (${item.id.slice(0, 12)}…)`);
    } catch (err) {
      setWatchMsg(err instanceof Error ? err.message : "Failed to add watch");
    } finally {
      setWatching(false);
    }
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
            <span className="text-[var(--border)]">|</span>
            <Link href="/watchlist" className="hover:text-[var(--ink)]">
              Watchlist
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleWatchTopic}
              disabled={watching}
              className="text-xs text-[var(--link)] hover:underline disabled:opacity-50"
            >
              {watching ? "Adding…" : "Watch this topic"}
            </button>
            {report.metadata && (
              <p className="text-xs text-[var(--muted)] tabular-nums">
                {report.metadata.execution_time_seconds.toFixed(0)}s ·{" "}
                {displaySourceCount} sources · {report.facts.length} facts
              </p>
            )}
          </div>
        </div>
        {watchMsg && (
          <div className={`${PAGE_GUTTER} pb-2 text-xs text-[var(--muted)]`}>
            {watchMsg.includes("/watchlist") ? (
              <>
                Watching —{" "}
                <Link href="/watchlist" className="text-[var(--link)] hover:underline">
                  open watchlist
                </Link>
              </>
            ) : (
              watchMsg
            )}
          </div>
        )}
      </header>

      <div className={`${PAGE_GUTTER} py-12 sm:py-14`}>
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
            <span className="report-section-label">{labels.overview}</span>
            <h2 className="font-display brief-section-title text-[var(--ink)] mb-5">
              {labels.conclusion}
            </h2>
            <div className="report-lead">
              <p className="font-display text-2xl md:text-3xl leading-snug text-[var(--ink)]">
                {thesis}
              </p>
              {legacySummary ? (
                <p className="brief-summary text-[var(--muted)] mt-5">{legacySummary}</p>
              ) : null}
            </div>
          </section>

          {hasStructuredArgs ? (
            <Section label={labels.evidence} title={labels.arguments}>
              <ArgumentsList arguments={argumentsList} onCitationClick={openCitation} />
            </Section>
          ) : report.facts.length > 0 ? (
            <Section label={labels.evidence} title={labels.arguments}>
              <ArgumentsList
                arguments={report.facts.slice(0, 6).map((f, i) => ({
                  claim: f.fact,
                  detail: "",
                  citation_indices: [i + 1],
                  confidence: f.confidence,
                }))}
                onCitationClick={openCitation}
              />
            </Section>
          ) : null}

          {report.gaps ? (
            <Section label={zh ? "范围" : "Scope"} title={labels.limits}>
              <p className="brief-body text-[var(--ink)]/85">{report.gaps}</p>
              {report.coverage ? (
                <p className="mt-4 text-sm text-[var(--muted)] leading-relaxed">
                  <span className="uppercase tracking-wider text-xs mr-2">
                    {labels.coverage}
                  </span>
                  {report.coverage}
                </p>
              ) : null}
            </Section>
          ) : report.coverage ? (
            <Section label={zh ? "范围" : "Scope"} title={labels.coverage}>
              <p className="brief-body text-[var(--ink)]/85">{report.coverage}</p>
            </Section>
          ) : null}

          {isInvestorBrief && report.fund_activity && (
            <Section label={zh ? "产品" : "Products"} title="Fund & Product Activity">
              <p className="brief-body text-[var(--ink)]/90 whitespace-pre-wrap">
                {report.fund_activity}
              </p>
            </Section>
          )}

          {isInvestorBrief && report.credit_risk_watch && (
            <Section label={zh ? "风险" : "Risk"} title="Credit Risk Watch">
              <p className="brief-body text-[var(--ink)]/90 whitespace-pre-wrap">
                {report.credit_risk_watch}
              </p>
            </Section>
          )}

          <Section label={labels.sources} title={labels.sources} className="pb-4">
            <ul className="space-y-5 brief-body list-none">
              {groupedSources.map((src) => {
                const host = (() => {
                  try {
                    return new URL(src.url).hostname.replace(/^www\./, "");
                  } catch {
                    return src.url;
                  }
                })();
                return (
                  <li key={normalizeUrl(src.url)} className="min-w-0">
                    <button
                      type="button"
                      onClick={() => openCitation(src.indices[0])}
                      className="text-[var(--link)] hover:underline text-left font-medium"
                    >
                      {src.name || host}
                    </button>
                    <p className="text-xs text-[var(--muted)] mt-0.5">
                      {host}
                      {" · "}
                      {zh
                        ? `支撑 ${src.indices.length} 处`
                        : `Supports ${src.indices.length} claim${src.indices.length > 1 ? "s" : ""}`}
                    </p>
                    <p className="text-[var(--muted)] mt-1.5 italic leading-relaxed text-sm">
                      &ldquo;{src.quote.slice(0, 160)}
                      {src.quote.length > 160 ? "…" : ""}&rdquo;
                    </p>
                  </li>
                );
              })}
            </ul>
          </Section>

          {showLedger ? (
            <details className="report-section group pb-8">
              <summary className="cursor-pointer list-none">
                <span className="report-section-label">{zh ? "附录" : "Appendix"}</span>
                <h2 className="font-display brief-section-title text-[var(--ink)] mb-2 inline-block">
                  {labels.ledger}
                </h2>
                <span className="ml-3 text-xs text-[var(--muted)] group-open:hidden">
                  {zh ? "展开" : "Expand"}
                </span>
              </summary>
              <div className="mt-4">
                <FindingsTable rows={tableRows} onCitationClick={openCitation} />
              </div>
            </details>
          ) : null}
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
