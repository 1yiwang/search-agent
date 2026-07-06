import { isPrivateAppHost } from "./hosts";

/** Public tunnel URL when the personal API is running locally. */
const PRODUCTION_API = "https://api-search.yiwang.dev";

/**
 * Base URL for FastAPI. Empty string = same-origin `/api/*` (Next.js rewrite to localhost in dev).
 * Production must call the tunnel directly — Vercel rewrites break SSE research streams.
 */
export function getApiBase(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
  if (fromEnv) return fromEnv;

  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (isPrivateAppHost(host)) return PRODUCTION_API;
  }

  return "";
}
