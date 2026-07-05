import type { NextConfig } from "next";

const apiUrl = process.env.API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  /**
   * Proxy /api/* to the FastAPI backend in dev/preview when NEXT_PUBLIC_API_URL is unset.
   * For long SSE research streams in production, prefer setting NEXT_PUBLIC_API_URL
   * to the public backend URL (avoids Vercel rewrite timeouts).
   */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
