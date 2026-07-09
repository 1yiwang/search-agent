/** Build Chrome/Edge Text Fragment URL for in-page highlight on the original site. */

function pickFragmentText(quote: string, anchor: string): string {
  const raw = (quote || anchor || "").replace(/\s+/g, " ").trim();
  if (!raw) return "";

  if (raw.length <= 80) return raw;

  const start = raw.slice(0, 40).trim();
  const end = raw.slice(-40).trim();
  if (start.length >= 20 && end.length >= 20 && start !== end) {
    return `${start},${end}`;
  }
  return raw.slice(0, 80).trim();
}

export function buildTextFragmentUrl(
  url: string,
  quote: string,
  anchor?: string
): string {
  const fragment = pickFragmentText(quote, anchor || "");
  if (!fragment) return url;

  const base = url.split("#")[0];
  const encoded = encodeURIComponent(fragment)
    .replace(/-/g, "%2D")
    .replace(/'/g, "%27")
    .replace(/\(/g, "%28")
    .replace(/\)/g, "%29")
    .replace(/~/g, "%7E");

  return `${base}#:~:text=${encoded}`;
}
