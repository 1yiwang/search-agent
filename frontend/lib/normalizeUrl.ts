/** URL normalization aligned with backend dedup.normalize_url */

export function normalizeUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./i, "");
    const path = parsed.pathname.replace(/\/$/, "") || "";
    return `${host}${path}${parsed.search}`;
  } catch {
    return url.trim();
  }
}

export function domainFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./i, "").toLowerCase();
  } catch {
    return "";
  }
}

export function countUniqueDomains(urls: string[]): number {
  const domains = new Set<string>();
  for (const url of urls) {
    const d = domainFromUrl(url);
    if (d) domains.add(d);
  }
  return domains.size;
}
