import type { NextConfig } from "next";

/** FastAPI URL as seen from the Next.js server (Docker: http://backend:8080). Used only for rewrites. */
const backendInternal =
  process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8080";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/health", destination: `${backendInternal}/health` },
      { source: "/api/:path*", destination: `${backendInternal}/api/:path*` },
    ];
  },
};

export default nextConfig;
