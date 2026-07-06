"use client";

import type { Citation } from "@/lib/api";
import {
  excerptAround,
  findHighlightRange,
  isDownloadableUrl,
  type SourceSnapshot,
} from "@/lib/sourcePreview";

export function CitationPanel({
  citation,
  snapshot,
  onClose,
}: {
  citation: Citation;
  snapshot?: SourceSnapshot;
  onClose: () => void;
}) {
  const isDocument =
    snapshot?.content_kind === "document" || isDownloadableUrl(citation.source_url);
  const bodyText = snapshot?.text?.trim() || citation.quoted_text;
  const range = bodyText
    ? findHighlightRange(bodyText, citation.quoted_text, citation.highlight_anchor)
    : null;
  const excerpt = excerptAround(bodyText, range);

  return (
    <div className="rounded-xl border border-[var(--accent)]/30 bg-[var(--surface-raised)] p-5 shadow-lg max-h-[calc(100vh-8rem)] flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-3 shrink-0">
        <h3 className="text-sm font-semibold text-[var(--ink)] leading-snug">
          [{citation.index}] {citation.source_name}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--ink)] text-lg leading-none shrink-0"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      {isDocument && (
        <p className="text-xs text-[var(--muted)] mb-3 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 shrink-0">
          此来源为 Word/PDF 等文件，无法在页内打开原件。下方为抓取时提取的文本。
        </p>
      )}

      <div className="overflow-y-auto flex-1 min-h-0 text-sm leading-relaxed text-[var(--ink)]/90">
        {bodyText ? (
          <p className="whitespace-pre-wrap">
            {excerpt.before}
            {excerpt.highlight ? (
              <mark className="bg-[var(--accent)]/25 text-[var(--ink)] rounded px-0.5">
                {excerpt.highlight}
              </mark>
            ) : null}
            {excerpt.after}
          </p>
        ) : (
          <blockquote className="border-l-2 border-[var(--accent)] pl-3 text-[var(--muted)] italic">
            &ldquo;{citation.quoted_text}&rdquo;
          </blockquote>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-[var(--border)] shrink-0 flex flex-wrap gap-3 text-xs">
        {!isDocument && (
          <a
            href={citation.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--link)] hover:underline"
          >
            在新标签页打开原文 →
          </a>
        )}
        {isDocument && (
          <a
            href={citation.source_url}
            target="_blank"
            rel="noopener noreferrer"
            download
            className="text-[var(--muted)] hover:text-[var(--ink)] hover:underline"
          >
            下载原文件（可选）
          </a>
        )}
      </div>
    </div>
  );
}
