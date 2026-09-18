// Next.js 15.3+ loads browser instrumentation from this file. Keeping the real
// configuration in sentry.client.config.ts means there is still one place to edit.
import * as Sentry from "@sentry/nextjs";

import "./sentry.client.config";

// Required by @sentry/nextjs 10.x to trace client-side route changes. A no-op when Sentry
// was never initialised (no DSN), so this is safe regardless of environment.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
