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
  const excerpt = excerptAround(text, range, 360);

  return (
    <div className="citation-reader text-[var(--ink)]/90 text-[13px] leading-relaxed">
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
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-3 shadow-md max-h-[min(70vh,calc(100vh-7rem))] flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-2 shrink-0">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] uppercase tracking-wider text-[var(--accent)] mb-0.5">
            Source [{citation.index}]
          </p>
          <h3 className="text-xs font-medium text-[var(--ink)] leading-snug line-clamp-2">
            {citation.source_name}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--ink)] text-base leading-none shrink-0 p-0.5"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      {isDocument && (
        <p className="text-[10px] text-[var(--muted)] mb-2 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 shrink-0 leading-snug">
          Word/PDF 文件无法在页内预览，下方为提取文本。
        </p>
      )}

      <div className="overflow-y-auto flex-1 min-h-0 pr-0.5">
        {bodyText ? (
          <ReaderBody
            text={bodyText}
            quoted={citation.quoted_text}
            anchor={citation.highlight_anchor}
          />
        ) : (
          <blockquote className="border-l-2 border-[var(--accent)] pl-2 text-[var(--muted)] italic text-xs">
            &ldquo;{citation.quoted_text}&rdquo;
          </blockquote>
        )}
      </div>

      <div className="mt-2 pt-2 border-t border-[var(--border)] shrink-0 flex flex-col gap-1.5 text-[10px]">
        {!isDocument && (
          <>
            <a
              href={highlightUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center rounded border border-[var(--accent)]/35 bg-[var(--accent)]/10 px-2 py-1.5 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors text-center leading-tight"
            >
              新标签页打开并高亮
            </a>
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--link)] hover:underline text-center"
            >
              打开原文
            </a>
          </>
        )}
        {isDocument && (
          <a
            href={citation.source_url}
            target="_blank"
            rel="noopener noreferrer"
            download
            className="text-[var(--muted)] hover:text-[var(--ink)] hover:underline text-center"
          >
            下载原文件
          </a>
        )}
      </div>
    </div>
  );
}
