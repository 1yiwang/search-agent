"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "@/lib/api";
import {
  excerptAround,
  findHighlightRange,
  isDownloadableUrl,
  type SourceSnapshot,
} from "@/lib/sourcePreview";
import { buildTextFragmentUrl } from "@/lib/textFragmentUrl";

function MarkdownChunk({ text }: { text: string }) {
  if (!text.trim()) return null;
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
  );
}

function ReaderBody({
  text,
  quoted,
  anchor,
}: {
  text: string;
  quoted: string;
  anchor: string;
}) {
  const range = findHighlightRange(text, quoted, anchor);
  const excerpt = excerptAround(text, range, 600);

  return (
    <div className="citation-reader text-[var(--ink)]/90">
      <MarkdownChunk text={excerpt.before} />
      {excerpt.highlight ? (
        <mark className="bg-[var(--accent)]/25 text-[var(--ink)] rounded px-0.5">
          {excerpt.highlight}
        </mark>
      ) : null}
      <MarkdownChunk text={excerpt.after} />
    </div>
  );
}

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
  const highlightUrl = buildTextFragmentUrl(
    citation.source_url,
    citation.quoted_text,
    citation.highlight_anchor
  );

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

      <div className="overflow-y-auto flex-1 min-h-0">
        {bodyText ? (
          <ReaderBody
            text={bodyText}
            quoted={citation.quoted_text}
            anchor={citation.highlight_anchor}
          />
        ) : (
          <blockquote className="border-l-2 border-[var(--accent)] pl-3 text-[var(--muted)] italic text-sm">
            &ldquo;{citation.quoted_text}&rdquo;
          </blockquote>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-[var(--border)] shrink-0 flex flex-col gap-2 text-xs">
        {!isDocument && (
          <>
            <a
              href={highlightUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center rounded-md border border-[var(--accent)]/40 bg-[var(--accent)]/10 px-3 py-2 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors"
            >
              在新标签页打开并高亮 →
            </a>
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--link)] hover:underline"
            >
              打开原文（无高亮）
            </a>
            <p className="text-[var(--muted)] leading-relaxed">
              高亮依赖浏览器 Text Fragment；PDF 或动态页面可能无法定位。
            </p>
          </>
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
