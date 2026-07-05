"use client";

import { useCallback, useEffect, useState } from "react";
import type { Citation, ResearchReport } from "@/lib/api";

export function DemoReportView({ report }: { report: ResearchReport }) {
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  const renderMarkdown = useCallback((markdown: string) => {
    const sanitizeHtml = (html: string): string =>
      html
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
        .replace(/<iframe\b[^>]*>.*?<\/iframe>/gi, "")
        .replace(/<iframe\b[^>]*\/?>/gi, "")
        .replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, "")
        .replace(/\s+on\w+\s*=\s*[^\s>]+/gi, "")
        .replace(/href\s*=\s*["']javascript:[^"']*["']/gi, 'href="#"')
        .replace(/src\s*=\s*["']javascript:[^"']*["']/gi, 'src=""');

    let html = markdown
      .replace(
        /\[\^(\d+)\]/g,
        (_, num) =>
          `<sup><span class="citation-link citation-mark" data-index="${num}" style="cursor:pointer;">[${num}]</span></sup>`,
      )
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-6 mb-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold mt-8 mb-3">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>')
      .replace(
        /\[([^\]]+)\]\(([^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener" class="text-blue-400 hover:underline">$1</a>',
      )
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
      .replace(/\n\n/g, "</p><p class='my-2'>")
      .replace(/\n/g, "<br/>")
      .replace(/^---$/gm, '<hr class="my-6 border-zinc-700"/>');

    html = `<p class='my-2'>${html}</p>`;
    return sanitizeHtml(html);
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("citation-link")) {
        const index = parseInt(target.dataset.index || "0", 10);
        const citation = report.citations.find((c) => c.index === index);
        if (citation) setActiveCitation(citation);
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [report]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-12">
      <div className="flex gap-8">
        <article className="flex-1 min-w-0">
          {report.metadata && (
            <div className="mb-8 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-sm text-zinc-500">
              ⏱ {report.metadata.execution_time_seconds.toFixed(1)}s · 🔗{" "}
              {report.metadata.source_count} sources · Demo (static)
            </div>
          )}
          <div
            className="prose prose-invert prose-zinc max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(report.markdown) }}
          />
        </article>

        {activeCitation && (
          <aside className="w-96 flex-shrink-0 sticky top-4 self-start">
            <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm">
                  📎 [{activeCitation.index}] {activeCitation.source_name}
                </h3>
                <button
                  type="button"
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
                Open source →
              </a>
            </div>
          </aside>
        )}
      </div>
    </main>
  );
}
