# Ad Spend Optimization — web image (CSC418 lab build).

FROM node:24-slim

WORKDIR /app

# BACKEND_URL has to be an ARG, not only a runtime variable: next.config.ts reads it while
# `next build` runs and writes the /api/:path* rewrite into routes-manifest.json, so a value set
# only at run time would never reach the compiled routing table.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}

# `next build` is the memory-hungry step of this image. Capping the V8 heap makes an
# out-of-memory build fail with a JavaScript error instead of being killed by the kernel, which is
# the difference between a readable log and a container that simply disappears on a 4 GiB host.
ENV NODE_OPTIONS=--max-old-space-size=1536

# Lockfile install first, for the same reason as the backend: source edits reuse this layer.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN npm run build

EXPOSE 3000

# `next start` binds 0.0.0.0 by default in this version; the flag states it rather than relying on
# a default, because a target group cannot reach a server that bound itself to loopback.
CMD ["npm", "start", "--", "-H", "0.0.0.0"]
