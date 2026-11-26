import type { NextConfig } from "next";

// The browser talks to the API through this app at /api (same origin), so the session cookie is first-party
// on any host (Vercel, Cloud Run, a custom domain) and no CORS preflights are needed.
// API_ORIGIN is read at build time: set it before `next build`.
const apiOrigin = (process.env.API_ORIGIN || "http://localhost:8000").replace(/\/$/, "");
if (process.env.VERCEL && !process.env.API_ORIGIN && !process.env.NEXT_PUBLIC_API_URL) {
  // Without it every /api call would go to localhost and the deployed app couldn't sign anyone in.
  throw new Error("Set API_ORIGIN in the Vercel project (your Cloud Run API URL) and redeploy.");
}

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  output: "standalone", // self-contained server for the Docker image; Vercel ignores it
  // The footer's copyright year, fixed at build time (pages can't read the clock while prerendering).
  env: { NEXT_PUBLIC_BUILD_YEAR: String(new Date().getFullYear()) },
  poweredByHeader: false,
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // The self-hosted proxy drops a request after 30s of silence by default; AI rewrites and images can take longer.
    // Streams send a keep-alive ping every 15s. (On Vercel the platform's own proxy limits apply instead.)
    proxyTimeout: 15 * 60_000,
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
