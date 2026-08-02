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
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>;
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
  const excerpt = excerptAround(text, range, 480);

  return (
    <div className="citation-reader text-[var(--ink)]/90 text-sm leading-relaxed">
      <MarkdownChunk text={excerpt.before} />
      {excerpt.highlight ? (
        <mark className="bg-[var(--accent)]/30 text-[var(--ink)] rounded px-0.5">
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
  variant = "modal",
}: {
  citation: Citation;
  snapshot?: SourceSnapshot;
  onClose: () => void;
  variant?: "modal" | "inline";
}) {
  const isDocument =
    snapshot?.content_kind === "document" || isDownloadableUrl(citation.source_url);
  const bodyText = snapshot?.text?.trim() || citation.quoted_text;
  const highlightUrl = buildTextFragmentUrl(
    citation.source_url,
    citation.quoted_text,
    citation.highlight_anchor
  );

  const shell =
    variant === "modal"
      ? "rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] shadow-2xl flex flex-col h-full max-h-[min(88vh,640px)]"
      : "rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-3 shadow-md max-h-[min(70vh,calc(100vh-7rem))] flex flex-col";

  return (
    <div className={shell}>
      <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-3 shrink-0 border-b border-[var(--border)]">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] uppercase tracking-wider text-[var(--signal)] mb-1">
            Source [{citation.index}]
          </p>
          <h3
            id="citation-modal-title"
            className="text-sm font-medium text-[var(--ink)] leading-snug"
          >
            {citation.source_name}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--muted)] hover:text-[var(--ink)] hover:border-[var(--accent)]/40 transition-colors shrink-0"
          aria-label="关闭"
        >
          关闭
        </button>
      </div>

      {isDocument && (
        <p className="text-xs text-[var(--muted)] mx-5 mt-3 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 shrink-0 leading-snug">
          Word/PDF 文件无法在页内预览，下方为提取文本。
        </p>
      )}

      <div className="overflow-y-auto flex-1 min-h-0 px-5 py-4">
        {bodyText ? (
          <ReaderBody
            text={bodyText}
            quoted={citation.quoted_text}
            anchor={citation.highlight_anchor}
          />
        ) : (
          <blockquote className="border-l-2 border-[var(--signal)] pl-3 text-[var(--muted)] italic text-sm">
            &ldquo;{citation.quoted_text}&rdquo;
          </blockquote>
        )}
      </div>

      <div className="px-5 py-4 border-t border-[var(--border)] shrink-0 flex flex-wrap gap-2 text-xs">
        {!isDocument && (
          <>
            <a
              href={highlightUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center rounded-md border border-[var(--signal)]/40 bg-[var(--signal)]/10 px-3 py-2 text-[var(--signal)] hover:bg-[var(--signal)]/15 transition-colors"
            >
              新标签页打开并高亮
            </a>
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center rounded-md border border-[var(--border)] px-3 py-2 text-[var(--link)] hover:bg-[var(--surface)] transition-colors"
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
            className="text-[var(--link)] hover:underline"
          >
            下载原文件
          </a>
        )}
      </div>
    </div>
  );
}
