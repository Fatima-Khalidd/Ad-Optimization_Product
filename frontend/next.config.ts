import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

// Opt-in, not global: the self-contained `.next/standalone` server bundle is only what
// frontend/Dockerfile copies. The Vercel build of this app predates it and must keep
// building exactly as before, so the Docker build stage sets NEXT_STANDALONE_OUTPUT=1.
if (process.env.NEXT_STANDALONE_OUTPUT === "1") {
  nextConfig.output = "standalone";
}

// Without a DSN the plugin would still try to resolve an org/project at build time,
// so local builds and CI use the bare config.
export default process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(nextConfig, {
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      silent: true,
      widenClientFileUpload: true,
      disableLogger: true,
      // Source maps are uploaded to Sentry, then removed from the deployed bundle.
      sourcemaps: { deleteSourcemapsAfterUpload: true },
    })
  : nextConfig;
