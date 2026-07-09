/** Helpers for in-app citation preview and text highlighting. */

import { normalizeUrl } from "./normalizeUrl";

export interface SourceSnapshot {
  url: string;
  title: string;
  content_kind: "html" | "document" | "empty";
  text: string;
  normalized_url?: string;
}

const DOWNLOAD_EXT = /\.(docx?|pdf|xlsx?|pptx?)(\?|#|$)/i;

export function isDownloadableUrl(url: string): boolean {
  return DOWNLOAD_EXT.test(url);
}

export interface HighlightRange {
  start: number;
  end: number;
}

/** Find best substring match for quoted text or anchor in source body. */
export function findHighlightRange(
  text: string,
  quoted: string,
  anchor: string
): HighlightRange | null {
  const needles = [quoted, anchor, quoted.slice(0, 80), anchor.slice(0, 50)].filter(
    (n) => n.trim().length >= 6
  );

  for (const needle of needles) {
    const idx = text.indexOf(needle);
    if (idx >= 0) return { start: idx, end: idx + needle.length };
  }

  const lower = text.toLowerCase();
  for (const needle of needles) {
    const idx = lower.indexOf(needle.toLowerCase());
    if (idx >= 0) return { start: idx, end: idx + needle.length };
  }

  return null;
}

/** Slice text around a highlight with ellipsis when truncated. */
export function excerptAround(
  text: string,
  range: HighlightRange | null,
  context = 420
): { before: string; highlight: string; after: string } {
  if (!text) {
    return { before: "", highlight: "", after: "" };
  }

  if (!range) {
    const slice = text.slice(0, context * 2);
    return {
      before: slice,
      highlight: "",
      after: text.length > slice.length ? "…" : "",
    };
  }

  const start = Math.max(0, range.start - context);
  const end = Math.min(text.length, range.end + context);
  return {
    before: (start > 0 ? "…" : "") + text.slice(start, range.start),
    highlight: text.slice(range.start, range.end),
    after: text.slice(range.end, end) + (end < text.length ? "…" : ""),
  };
}

export function snapshotForUrl(
  snapshots: SourceSnapshot[] | undefined,
  url: string
): SourceSnapshot | undefined {
  if (!snapshots?.length) return undefined;
  const key = normalizeUrl(url);
  return (
    snapshots.find((s) => (s.normalized_url && s.normalized_url === key) || normalizeUrl(s.url) === key) ||
    snapshots.find((s) => s.url === url)
  );
}
