import type { NextConfig } from "next";

const apiUrl = process.env.API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  /**
   * Dev: proxy unmatched /api/* to local FastAPI (SSE streams, health).
   * Vercel: no rewrites — App Router owns /api/reports & /api/research/[slug];
   * research streams call api-search.yiwang.dev directly from the browser.
   */
  async rewrites() {
    if (process.env.VERCEL) {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
