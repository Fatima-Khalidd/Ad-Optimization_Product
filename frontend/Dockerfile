# Task 3 (frontend image): the Next.js web tier, built into a standalone server so the
# runtime stage never ships node_modules.
#
# Stage names: deps -> build -> runtime.
# Node 24 matches the frontend job in .github/workflows/ci.yml.

FROM node:24-alpine AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Lockfile first: npm ci is reproducible and this layer survives source edits.
COPY package.json package-lock.json ./
RUN npm ci

# ------------------------------------------------------------------- build ----
FROM deps AS build

# Baked into the rewritten /api/* routes at build time. Inside the Compose network the
# backend is always reachable as http://backend:8000, on a laptop and on EC2 alike, so
# this default never needs changing; override with --build-arg only for an external API.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
# next.config.ts only emits .next/standalone when this is set, so the Vercel build of the
# same file is unaffected. The runtime stage below depends on that folder existing.
ENV NEXT_STANDALONE_OUTPUT=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ----------------------------------------------------------------- runtime ----
FROM node:24-alpine AS runtime
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public

USER node
EXPOSE 3000

# Going through the app's own /api/* rewrite means this check only passes when the
# proxy hop to the backend container works too.
HEALTHCHECK --interval=15s --timeout=6s --start-period=30s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:3000/api/health || exit 1

CMD ["node", "server.js"]
