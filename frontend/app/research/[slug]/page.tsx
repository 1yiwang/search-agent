"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { getReport, type ResearchReport, type Citation } from "@/lib/api";

export default function ReportPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [report, setReport] = useState<ResearchReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    getReport(slug)
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [slug]);

  const renderMarkdown = useCallback((markdown: string) => {
    // Convert footnote-style citations [^1] to clickable links
    let html = markdown
      // Convert citation markers [^1] to clickable spans
      .replace(
        /\[\^(\d+)\]/g,
        (_, num) =>
          `<sup><span class="citation-link" data-index="${num}" style="cursor:pointer;color:#60a5fa;font-weight:600;">[${num}]</span></sup>`
      )
      // Convert markdown headers
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-6 mb-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold mt-8 mb-3">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>')
      // Convert markdown links
      .replace(
        /\[([^\]]+)\]\(([^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener" class="text-blue-400 hover:underline">$1</a>'
      )
      // Convert bold
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      // Convert italic
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      // Convert list items
      .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
      // Convert paragraphs (double newlines)
      .replace(/\n\n/g, "</p><p class='my-2'>")
      // Convert single newlines
      .replace(/\n/g, "<br/>")
      // Convert horizontal rules
      .replace(/^---$/gm, '<hr class="my-6 border-zinc-700"/>');

    html = `<p class='my-2'>${html}</p>`;
    return html;
  }, []);

  // Handle citation clicks
  useEffect(() => {
    if (!report) return;

    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("citation-link")) {
        const index = parseInt(target.dataset.index || "0", 10);
        const citation = report.citations.find((c) => c.index === index);
        if (citation) {
          setActiveCitation(citation);
        }
      }
    };

    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [report]);

  if (loading) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-20 text-center text-zinc-400">
        Loading report...
      </main>
    );
  }

  if (error || !report) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-20 text-center text-red-400">
        {error || "Report not found"}
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-12">
      <div className="flex gap-8">
        {/* Report content */}
        <article className="flex-1 min-w-0">
          <a href="/" className="text-sm text-zinc-500 hover:text-zinc-300 mb-4 inline-block">
            ← New search
          </a>

          {/* Trust signals */}
          {report.metadata && (
            <div className="mb-8 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-sm text-zinc-500 space-y-1">
              <div>⏱ {(report.metadata.execution_time_seconds).toFixed(1)}s · 🔗 {report.metadata.source_count} sources</div>
            </div>
          )}

          <div
            className="prose prose-invert prose-zinc max-w-none"
            dangerouslySetInnerHTML={{
              __html: renderMarkdown(report.markdown),
            }}
          />
        </article>

        {/* Citation sidebar */}
        {activeCitation && (
          <aside className="w-96 flex-shrink-0 sticky top-4 self-start">
            <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm">
                  📎 [{activeCitation.index}] {activeCitation.source_name}
                </h3>
                <button
                  onClick={() => setActiveCitation(null)}
                  className="text-zinc-500 hover:text-zinc-300"
                >
                  ✕
                </button>
              </div>
              <blockquote className="border-l-2 border-zinc-600 pl-3 text-sm text-zinc-400 italic mb-3">
                &ldquo;{activeCitation.quoted_text}&rdquo;
              </blockquote>
              <a
                href={activeCitation.source_url}
                target="_blank"
                rel="noopener"
                className="text-sm text-blue-400 hover:underline"
              >
                Open source in new tab →
              </a>
            </div>
          </aside>
        )}
      </div>

      {/* Source list at bottom */}
      <section className="mt-12 border-t border-zinc-800 pt-8">
        <h2 className="text-lg font-semibold mb-4">📚 Sources</h2>
        <ol className="space-y-2 text-sm text-zinc-400">
          {report.citations.map((c) => (
            <li key={c.index} id={`source-${c.index}`}>
              <span className="text-blue-400 font-semibold">[{c.index}]</span>{" "}
              <a
                href={c.source_url}
                target="_blank"
                rel="noopener"
                className="text-zinc-300 hover:underline"
              >
                {c.source_name}
              </a>
              <span className="text-zinc-600">
                {" "}— &ldquo;{c.quoted_text.slice(0, 150)}
                {c.quoted_text.length > 150 ? "..." : ""}&rdquo;
              </span>
            </li>
          ))}
        </ol>
      </section>

      {/* Show hint when no citation selected */}
      {!activeCitation && (
        <div className="fixed bottom-4 right-4 text-xs text-zinc-600 bg-zinc-900 px-3 py-2 rounded-lg border border-zinc-800">
          Click [ⁿ] citations to verify sources
        </div>
      )}
    </main>
  );
}
