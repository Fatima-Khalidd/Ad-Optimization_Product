# Stage 4 — Client Dashboard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A logged-in client can sign up, log in, drag a CSV onto the upload page, watch the analysis run, and — once an admin has approved it — read their waste report on an asymmetric dashboard whose hero is a one-shot particle flow (static SVG under `prefers-reduced-motion`), with per-dimension breakdown tables and expandable recommendations, working down to 400px wide.

**Architecture:** Next.js App Router. Anything that needs the httpOnly auth cookie *before* first paint is a **server component** that forwards the incoming request cookies to FastAPI over `BACKEND_URL` (`src/lib/server-api.ts`); anything interactive is a **client component** talking to the same API through the Next rewrite at `/api/*` with `credentials: "include"` (`src/lib/api.ts`). The report renderer is one component (`ReportView`) reused by `/dashboard`, `/dashboard/reports/[runId]` and — with `hero={false}` — by Stage 6's admin views. Three.js sits behind `next/dynamic(..., { ssr: false })` so the tables never wait on it.

**Tech Stack:** Next.js 16.3.5 (App Router, `src/`), React 19.2, TypeScript 5 strict, Tailwind v4 (`@theme` tokens from Stage 0), Framer Motion, React Three Fiber + drei + three, Vitest + React Testing Library + jsdom.

**Spec:** `docs/PLAN.md` §6 "Stage 4" (authoritative for the screen list), §2 repository layout, §5 API surface, §1 #8 (the `/api/*` rewrite); `docs/superpowers/plans/INTERFACES.md` §"Stage 4 — client dashboard (frontend)" (authoritative for every file path, component name and function signature below) plus its Stage 2/3 sections for the payloads consumed.

**Additions to `docs/superpowers/plans/INTERFACES.md`** (permitted by that file's opening paragraph — nothing is renamed):

- `src/lib/server-api.ts` — the server-side twin of `api.ts`: `backendUrl()`, `cookieHeader()`, `serverFetch<T>()`, `getMe()`, `getLatestReport()`, `getReport()`, `getUploads()`. INTERFACES describes this behaviour ("server component reads cookies and calls `GET /api/auth/me`") without naming a file.
- `src/lib/motion.ts` — `useReducedMotion()`, `REDUCED_MOTION_QUERY`, `HERO_DURATION_MS`.
- `format.ts` gains `humanizeSegment()` and `wasteShare()` beside the contracted `formatPKR`/`formatPct`.
- `api.ts` gains `extractIssues(detail: unknown): ValidationReport`.
- `types.ts` gains `Dimension`, `DIMENSIONS`, `DIMENSION_LABELS`, `RowIssue`, `ValidationReport`, `UserOut`, `ClientOut` — the pieces the contracted types are built from.
- **Assumed Stage 3 response shape:** `POST /api/uploads` answers `422` with `{"detail": {"errors": RowIssue[], "warnings": RowIssue[]}}` when the loader rejects the file outright. `extractIssues` degrades to a one-row table for any other shape, so a different Stage 3 choice cannot break this stage — but Stage 3's plan should honour it or update INTERFACES.

## Global Constraints

Copied from the spec's visual identity rules (`docs/PLAN.md` §6 Stage 4 and the Stage 0 plan's Global Constraints). Every task inherits these.

- **Colours, tokens only** — `ink #0B1220`, `surface #141C2E`, `teal #2DD4BF`, `coral #FF6B4A`, `paper #F4F6F8`, `slate #8891A5`. Use the Tailwind utilities `bg-ink`, `bg-surface`, `text-teal`, `text-coral`, `text-paper`, `text-slate` (and their `/NN` opacity variants). **Never** write a hex literal in a component — the only exception is the pair of hero files, which need real colour values for SVG gradients and Three.js colour buffers, and they read them from one exported constant.
- **Type** — Space Grotesk (`font-display`) for headlines and every number the client reads as a headline; Inter (`font-body`, the `body` default) for prose. Both are already loaded by `src/app/layout.tsx`.
- **Layout is asymmetric.** The hero takes about 60% of the first screen; the key numbers sit beside it as **large type, never inside cards** — no border, no background panel, no shadow around a number.
- **Tables use hairline dividers** — `divide-y divide-slate/20`, no zebra striping, no cell borders. Flagged rows are coral; not-significant rows are muted.
- **Exactly ONE bold animation in the whole product: the hero particle flow, once on load.** It runs ~4s and stops. No loop.
- **Framer Motion is only for user-triggered transitions** (the recommendation expand). No scroll-triggered animation anywhere. No hover animation on cards or rows — `transition-colors` on buttons, links and tabs is the only hover effect allowed.
- **`prefers-reduced-motion: reduce` gets the static SVG hero and no count-up.** Same information, no movement.
- **Admin views (Stage 6) reuse `ReportView`, `SegmentTable` and `RecommendationList` but never the hero** — hence `ReportView`'s `hero` prop, which also switches the count-up off.
- **Money renders only through `formatPKR`**, percentages only through `formatPct`. No ad-hoc `toFixed` in a component.
- **Responsive floor is 400px wide.** The hero and the numbers stack; tables scroll horizontally inside their own container; nothing else may cause a horizontal scrollbar.
- **Tenant safety:** the frontend never sends a `client_id`. Every client route is scoped by the cookie the backend reads (`docs/PLAN.md` §4 "Tenant isolation").
- **TDD with Vitest** for every component and helper: failing test → implement → run → commit. For React Three Fiber, test only the wrapper's reduced-motion branching with a mocked `matchMedia`; never boot WebGL in jsdom.
- Work on a branch: `git checkout -b stage-4-client-dashboard` before Task 1.

---

## File Structure

```
frontend/
├── package.json                      # + test scripts, + 9 dependencies
├── vitest.config.ts                  # jsdom, @ alias, setup file
├── vitest.setup.ts                   # jest-dom matchers, matchMedia stub
└── src/
    ├── app/
    │   ├── (auth)/login/page.tsx     # -> /login
    │   ├── (auth)/signup/page.tsx    # -> /signup
    │   └── dashboard/
    │       ├── layout.tsx            # SERVER auth guard + nav
    │       ├── page.tsx              # SERVER: latest report or empty state
    │       ├── upload/page.tsx       # SERVER shell around <UploadPanel/>
    │       └── reports/[runId]/page.tsx
    ├── components/
    │   ├── auth/AuthForm.tsx         # login + signup, one component
    │   ├── shell/DashboardNav.tsx
    │   ├── shell/LogoutButton.tsx
    │   ├── upload/UploadPanel.tsx    # drop zone, analyze, polling
    │   ├── upload/IssueTable.tsx     # row-level validation errors
    │   ├── hero/FlowStatic.tsx       # SVG, also the reduced-motion fallback
    │   ├── hero/FlowParticles.tsx    # R3F one-shot stream
    │   ├── hero/Hero.tsx             # chooses between the two
    │   ├── dashboard/ReportView.tsx  # the whole report, hero optional
    │   ├── dashboard/SummaryNumbers.tsx
    │   ├── dashboard/CountUp.tsx
    │   ├── tables/SegmentTable.tsx   # tabs per dimension
    │   ├── recommendations/RecommendationList.tsx
    │   └── ui/{Button,Field,Stat,EmptyState}.tsx
    └── lib/
        ├── api.ts                    # apiFetch, ApiError, extractIssues
        ├── server-api.ts             # cookie-forwarding fetch for server components
        ├── format.ts                 # formatPKR, formatPct, humanizeSegment, wasteShare
        ├── motion.ts                 # useReducedMotion, HERO_DURATION_MS
        └── types.ts                  # TS mirrors of the backend schemas
```

Tests live beside their subject as `<name>.test.ts(x)`. Nothing under `src/app/` is tested directly — pages are thin server shells whose logic lives in `src/lib/server-api.ts` and in the client components, both of which are tested.

---

### Task 1: Verify and complete the Stage 0 frontend scaffold

The frontend was generated but never committed, and Stage 0 Task 7 may have been left part-done. Bring it to exactly the state Stage 0 specified, then commit it — every later task builds on these tokens.

**Files:**
- Verify/Modify: `frontend/src/app/globals.css`
- Verify/Modify: `frontend/src/app/layout.tsx`
- Verify/Modify: `frontend/src/app/page.tsx`
- Verify/Modify: `frontend/next.config.ts`
- Verify/Create: `frontend/.env.example`

**Interfaces:**
- Consumes: the backend at `http://127.0.0.1:8000`.
- Produces: Tailwind utilities `bg-ink`, `bg-surface`, `text-teal`, `text-coral`, `text-paper`, `text-slate`, `font-display`, `font-body`; the `/api/:path*` → `BACKEND_URL` rewrite; `process.env.BACKEND_URL` for server components. Every later task depends on all of these.

(Scaffold verification is a TDD exception; the gate is lint + typecheck + build + one eyeball check.)

- [ ] **Step 1: Start the branch**

```bash
cd /d/ad-optimizer-project
git checkout -b stage-4-client-dashboard
git status --short
```
Expected: `?? frontend/` (the scaffold is untracked) and probably `?? docs/superpowers/plans/INTERFACES.md`. If `frontend/` is already tracked and clean, that is fine too — continue.

- [ ] **Step 2: Make `globals.css` match Stage 0 exactly**

`frontend/src/app/globals.css` — the file must be **exactly** this. Replace it if it differs by so much as one token:
```css
@import "tailwindcss";

@theme {
  --color-ink: #0b1220;
  --color-surface: #141c2e;
  --color-teal: #2dd4bf;
  --color-coral: #ff6b4a;
  --color-paper: #f4f6f8;
  --color-slate: #8891a5;

  --font-display: var(--font-space-grotesk), ui-sans-serif, system-ui, sans-serif;
  --font-body: var(--font-inter), ui-sans-serif, system-ui, sans-serif;
}

html {
  color-scheme: dark;
}

body {
  background-color: var(--color-ink);
  color: var(--color-paper);
  font-family: var(--font-body);
}

h1,
h2,
h3,
.numeral {
  font-family: var(--font-display);
}
```

- [ ] **Step 3: Make `layout.tsx` match Stage 0 exactly**

`frontend/src/app/layout.tsx`:
```tsx
import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ad Spend Optimization",
  description: "Find and stop wasted ad spend.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${inter.variable}`}>
      <body className="min-h-screen bg-ink text-paper antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 4: Make `page.tsx` match Stage 0 exactly**

`frontend/src/app/page.tsx`:
```tsx
export default function Home() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-24">
      <p className="text-sm uppercase tracking-widest text-slate">Ad Spend Optimization</p>
      <h1 className="font-display text-5xl">Find the money leaking out of your ads.</h1>
      <p className="max-w-xl text-slate">
        Scaffold only — the dashboard arrives in Stage 4. Backend health:{" "}
        <a className="text-teal underline" href="/api/health">
          /api/health
        </a>
      </p>
    </main>
  );
}
```
(Task 12 rewrites this landing page to point at `/login` and `/signup`. Leave it alone until then.)

- [ ] **Step 5: Make `next.config.ts` and `.env.example` match Stage 0 exactly**

`frontend/next.config.ts`:
```ts
import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
```

`frontend/.env.example`:
```dotenv
# Where the FastAPI backend runs. Used server-side by next.config.ts rewrites.
BACKEND_URL=http://127.0.0.1:8000
```

- [ ] **Step 6: Prove the tokens really compile into utilities**

Temporarily add `<span className="bg-surface font-display text-coral">token check</span>` inside `page.tsx`'s `<main>`, then:
```bash
cd /d/ad-optimizer-project/frontend
npm run dev
```
Open http://localhost:3000. Expected: "token check" is **coral** on a **lighter navy** background in Space Grotesk. If it is plain paper-on-ink, the `@theme` block in Step 2 did not take — recheck the file. Stop the dev server and **delete the temporary span**.

- [ ] **Step 7: Lint, typecheck, build**

```bash
cd /d/ad-optimizer-project/frontend
npm run lint && npx tsc --noEmit && npm run build
```
Expected: eslint prints no errors, `tsc` prints nothing, the build ends with a `Route (app)` table listing `/`.

- [ ] **Step 8: Commit the scaffold**

```bash
cd /d/ad-optimizer-project
git add frontend docs/superpowers/plans
git commit -m "feat(frontend): Next.js scaffold with design tokens, fonts and API proxy"
git show --stat --name-only HEAD | grep -c node_modules
```
Expected: the `grep -c` prints `0` — Stage 0's `.gitignore` keeps `node_modules/` out. If it prints anything else, unstage and fix `.gitignore` before continuing.

---

### Task 2: Vitest + React Testing Library harness

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Test: `frontend/src/lib/smoke.test.tsx` (deleted again in Step 7)

**Interfaces:**
- Consumes: nothing.
- Produces: `npm test` → `vitest run`; `npm run test:watch` → `vitest`. A jsdom environment with `@testing-library/jest-dom` matchers, a writable `window.matchMedia` stub, and the `@/` alias resolving to `src/`. Every later task's tests rely on all of this. Also installs `framer-motion`, `three`, `@react-three/fiber`, `@react-three/drei` for Tasks 8–10.

- [ ] **Step 1: Look up the current versions**

You cannot know today's version numbers — ask npm:
```bash
cd /d/ad-optimizer-project/frontend
for p in vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom @testing-library/jest-dom @testing-library/user-event framer-motion three @react-three/fiber @react-three/drei @types/three; do echo "$p $(npm view $p version)"; done
```
Expected: one `name version` line per package. Install the latest of each in the next two steps (plain `npm install <pkg>` already takes the latest).

- [ ] **Step 2: Install the test tooling**

```bash
cd /d/ad-optimizer-project/frontend
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom @testing-library/jest-dom @testing-library/user-event
```
Expected: `added N packages`. `@testing-library/dom` is **not** optional — React Testing Library v16+ declares it as a peer dependency, and omitting it makes every `render()` throw `Cannot find module '@testing-library/dom'`.

- [ ] **Step 3: Install the animation dependencies now, so one install covers the whole stage**

```bash
cd /d/ad-optimizer-project/frontend
npm install framer-motion three @react-three/fiber @react-three/drei
npm install -D @types/three
```
Expected: `added N packages` and no `ERESOLVE` error. If npm reports a peer conflict against React 19, pin the React-19 majors explicitly — `npm install @react-three/fiber@^9 @react-three/drei@^10` — because `@react-three/fiber@8` supports React 18 only. Do **not** reach for `--force` or `--legacy-peer-deps`.

- [ ] **Step 4: Write the Vitest config**

`frontend/vitest.config.ts`:
```ts
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    unstubGlobals: true,
    unstubEnvs: true,
  },
});
```
`globals: false` is deliberate: every test imports `describe`/`it`/`expect`/`vi` from `"vitest"` explicitly, so `tsconfig.json` needs no `types` array and Next's own type setup stays untouched. `restoreMocks`/`unstubGlobals`/`unstubEnvs` mean no test has to clean up its own stubs.

- [ ] **Step 5: Write the setup file**

`frontend/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no matchMedia. Default to "motion is allowed"; the tests that care
// overwrite window.matchMedia themselves, which is why this is writable.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList,
});

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 6: Add the scripts**

In `frontend/package.json`, the `"scripts"` block becomes:
```json
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint",
    "test": "vitest run",
    "test:watch": "vitest"
  },
```

- [ ] **Step 7: Prove the harness works, then delete the smoke test**

`frontend/src/lib/smoke.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("test harness", () => {
  it("renders JSX into jsdom and has jest-dom matchers", () => {
    render(<p className="text-teal">harness ok</p>);

    expect(screen.getByText("harness ok")).toBeInTheDocument();
    expect(screen.getByText("harness ok")).toHaveClass("text-teal");
  });

  it("stubs matchMedia", () => {
    expect(window.matchMedia("(prefers-reduced-motion: reduce)").matches).toBe(false);
  });
});
```

```bash
cd /d/ad-optimizer-project/frontend
npm test
```
Expected: `Test Files  1 passed (1)` and `Tests  2 passed (2)`. Then remove it — it has done its job:
```bash
rm src/lib/smoke.test.tsx
```

- [ ] **Step 8: Typecheck and commit**

```bash
cd /d/ad-optimizer-project/frontend
npm run lint && npx tsc --noEmit
```
Expected: no output from either. (`vitest.config.ts` and `vitest.setup.ts` fall inside `tsconfig.json`'s `**/*.ts` include, so they are typechecked too.)
```bash
cd /d/ad-optimizer-project
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/vitest.setup.ts
git commit -m "test(frontend): add Vitest + React Testing Library harness"
```

---

### Task 3: The lib layer — types, formatting, `apiFetch`

Three small files with no React in them. They are the vocabulary for every component that follows, so they come first and are tested hardest.

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/format.test.ts`
- Test: `frontend/src/lib/api.test.ts`

**Interfaces:**
- Consumes: the Stage 2/3 JSON shapes from `INTERFACES.md` (`MeOut`, `ReportOut`, `UploadOut`, `RunOut`).
- Produces:
  ```ts
  // types.ts
  type Dimension = "placement" | "age_group" | "time_slot";
  const DIMENSIONS: readonly Dimension[];
  const DIMENSION_LABELS: Record<Dimension, string>;
  interface SegmentOut, DimensionOut, RecommendationOut, ReportOut,
            RowIssue, ValidationReport, UploadOut, RunOut,
            UserOut, ClientOut, MeOut, PaymentOut, PaymentMethodOut, InvoiceOut
  // format.ts
  formatPKR(n: number): string          // "Rs. 84,000"
  formatPct(n: number): string          // "12.4%"  (input already 0..100)
  humanizeSegment(value: string): string // "audience_network" -> "Audience Network"
  wasteShare(headlineWaste: number, totalSpend: number): number   // 0..1, 0 when totalSpend <= 0
  // api.ts
  class ApiError extends Error { status: number; detail: unknown }
  apiFetch<T>(path: string, init?: RequestInit): Promise<T>
  extractIssues(detail: unknown): ValidationReport
  ```

- [ ] **Step 1: Write the failing formatting tests**

`frontend/src/lib/format.test.ts`:
```ts
import { describe, expect, it } from "vitest";

import { formatPKR, formatPct, humanizeSegment, wasteShare } from "./format";

describe("formatPKR", () => {
  it("groups thousands and prefixes the rupee label", () => {
    expect(formatPKR(84000)).toBe("Rs. 84,000");
    expect(formatPKR(1234567)).toBe("Rs. 1,234,567");
    expect(formatPKR(800)).toBe("Rs. 800");
  });

  it("rounds to whole rupees", () => {
    expect(formatPKR(1234.5)).toBe("Rs. 1,235");
    expect(formatPKR(1234.4)).toBe("Rs. 1,234");
  });

  it("handles zero, tiny and negative amounts", () => {
    expect(formatPKR(0)).toBe("Rs. 0");
    expect(formatPKR(0.2)).toBe("Rs. 0");
    expect(formatPKR(-2500)).toBe("-Rs. 2,500");
  });

  it("never renders NaN", () => {
    expect(formatPKR(Number.NaN)).toBe("Rs. 0");
    expect(formatPKR(Number.POSITIVE_INFINITY)).toBe("Rs. 0");
  });
});

describe("formatPct", () => {
  it("shows one decimal place", () => {
    expect(formatPct(12.44)).toBe("12.4%");
    expect(formatPct(0)).toBe("0.0%");
    expect(formatPct(100)).toBe("100.0%");
  });

  it("never renders NaN", () => {
    expect(formatPct(Number.NaN)).toBe("0.0%");
  });
});

describe("humanizeSegment", () => {
  it("turns snake_case into title case", () => {
    expect(humanizeSegment("audience_network")).toBe("Audience Network");
    expect(humanizeSegment("feed")).toBe("Feed");
  });

  it("leaves age buckets and time slots alone", () => {
    expect(humanizeSegment("18-24")).toBe("18-24");
    expect(humanizeSegment("")).toBe("");
  });
});

describe("wasteShare", () => {
  it("is waste over spend, clamped to 0..1", () => {
    expect(wasteShare(100000, 400000)).toBe(0.25);
    expect(wasteShare(500000, 400000)).toBe(1);
    expect(wasteShare(-10, 400000)).toBe(0);
  });

  it("is 0 when there is no spend", () => {
    expect(wasteShare(100, 0)).toBe(0);
    expect(wasteShare(100, Number.NaN)).toBe(0);
  });
});
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/lib/format.test.ts`
Expected: FAIL — `Failed to resolve import "./format"`.

- [ ] **Step 3: Write `types.ts`**

`frontend/src/lib/types.ts`:
```ts
/**
 * TypeScript mirrors of the backend Pydantic schemas.
 * Source of truth: docs/superpowers/plans/INTERFACES.md, Stage 2 and Stage 3.
 * Decimal fields are strings — Pydantic v2 serialises Decimal as a JSON string.
 */

export type Dimension = "placement" | "age_group" | "time_slot";

export const DIMENSIONS: readonly Dimension[] = ["placement", "age_group", "time_slot"];

export const DIMENSION_LABELS: Record<Dimension, string> = {
  placement: "Placement",
  age_group: "Age group",
  time_slot: "Time slot",
};

export interface SegmentOut {
  segment: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  cpa: number | null;
  ctr: number | null;
  cvr: number | null;
  roas: number | null;
  is_significant: boolean;
  is_flagged: boolean;
  wasted_spend: number;
  flag_reason: string | null;
}

export interface DimensionOut {
  dimension: Dimension;
  benchmark_cpa: number | null;
  total_spend: number;
  total_wasted_spend: number;
  segments: SegmentOut[];
}

export interface RecommendationOut {
  id: number;
  dimension: Dimension;
  segment_name: string;
  current_spend: number;
  recommended_cut: number;
  reason: string;
}

export interface ReportOut {
  run_id: number;
  upload_id: number;
  generated_at: string;
  date_range_start: string | null;
  date_range_end: string | null;
  total_spend: number;
  headline_waste: number;
  recovery_pct: number;
  dimensions: DimensionOut[];
  recommendations: RecommendationOut[];
  config_snapshot: Record<string, unknown>;
}

/** One loader complaint. `row` is 1-based and null for whole-file problems. */
export interface RowIssue {
  row: number | null;
  column: string | null;
  message: string;
}

export interface ValidationReport {
  errors: RowIssue[];
  warnings: RowIssue[];
}

export type UploadStatus = "uploaded" | "validated" | "failed";

export interface UploadOut {
  id: number;
  uploaded_at: string;
  original_filename: string;
  row_count: number | null;
  date_range_start: string | null;
  date_range_end: string | null;
  status: UploadStatus;
  validation_report: ValidationReport | null;
}

export type RunStatus = "queued" | "running" | "done" | "failed";
export type ReviewStatus = "pending" | "approved" | "rejected";

export interface RunOut {
  id: number;
  upload_id: number;
  status: RunStatus;
  review_status: ReviewStatus;
  headline_waste: number | null;
  error_message: string | null;
  created_at: string;
}

export interface UserOut {
  id: number;
  email: string;
  role: "client" | "admin";
  created_at: string;
}

export interface ClientOut {
  id: number;
  business_name: string;
  base_fee: string;
  performance_fee_pct: string;
}

export interface MeOut {
  user: UserOut;
  client: ClientOut | null;
}

/** Stage 7 payloads. Declared here because INTERFACES puts them in types.ts. */
export type PaymentMethodType = "jazzcash" | "easypaisa" | "nayapay" | "raast" | "bank_iban";

export interface PaymentMethodOut {
  id: number;
  type: PaymentMethodType;
  account_title: string;
  account_identifier: string;
  instructions: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface PaymentOut {
  id: number;
  method_type: PaymentMethodType;
  transaction_ref: string;
  amount: string;
  paid_at: string;
  status: "pending" | "confirmed" | "rejected";
  review_note: string | null;
}

export interface InvoiceOut {
  id: number;
  invoice_number: string;
  period_start: string;
  period_end: string;
  due_date: string | null;
  base_fee: string;
  confirmed_recovered_waste: string | null;
  performance_fee: string;
  total: string;
  amount_paid: string;
  status: "draft" | "issued" | "payment_submitted" | "paid" | "void";
  payments: PaymentOut[];
}
```

- [ ] **Step 4: Write `format.ts`**

`frontend/src/lib/format.ts`:
```ts
/**
 * Every rupee figure in the UI goes through formatPKR, and every percentage
 * through formatPct. Components must never format money themselves.
 */

/** Whole rupees with thousands separators: formatPKR(84000) -> "Rs. 84,000". */
export function formatPKR(n: number): string {
  if (!Number.isFinite(n)) return "Rs. 0";
  const rounded = Math.round(n);
  const sign = rounded < 0 ? "-" : "";
  return `${sign}Rs. ${Math.abs(rounded).toLocaleString("en-US")}`;
}

/**
 * One decimal place. The input is already a percentage, not a fraction —
 * ReportOut.recovery_pct is headline_waste / total_spend * 100.
 */
export function formatPct(n: number): string {
  if (!Number.isFinite(n)) return "0.0%";
  return `${n.toFixed(1)}%`;
}

/** "audience_network" -> "Audience Network"; "18-24" is left as it is. */
export function humanizeSegment(value: string): string {
  return value
    .split("_")
    .map((word) => (word.length > 0 ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
}

/** The 0..1 fraction of spend that is wasted. Drives the hero's teal/coral split. */
export function wasteShare(headlineWaste: number, totalSpend: number): number {
  if (!Number.isFinite(headlineWaste) || !Number.isFinite(totalSpend) || totalSpend <= 0) {
    return 0;
  }
  return Math.min(1, Math.max(0, headlineWaste / totalSpend));
}
```

- [ ] **Step 5: Run the formatting tests**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/lib/format.test.ts`
Expected: `Tests  10 passed (10)`.

- [ ] **Step 6: Write the failing `apiFetch` tests**

`frontend/src/lib/api.test.ts`:
```ts
import { describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, extractIssues } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(response: Response) {
  const mock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("apiFetch", () => {
  it("sends cookies and returns the parsed body", async () => {
    const mock = stubFetch(jsonResponse({ id: 7, status: "done" }));

    await expect(apiFetch<{ id: number }>("/api/runs/7")).resolves.toEqual({
      id: 7,
      status: "done",
    });
    expect(mock).toHaveBeenCalledWith("/api/runs/7", expect.objectContaining({ credentials: "include" }));
  });

  it("sets a JSON content type for string bodies", async () => {
    const mock = stubFetch(jsonResponse({ ok: true }));

    await apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify({ email: "a@b.pk" }) });

    const init = mock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("leaves FormData alone so the browser can set the multipart boundary", async () => {
    const mock = stubFetch(jsonResponse({ id: 1 }));
    const form = new FormData();
    form.append("file", new File(["a,b"], "ads.csv", { type: "text/csv" }));

    await apiFetch("/api/uploads", { method: "POST", body: form });

    const init = mock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Content-Type")).toBeNull();
  });

  it("returns undefined for 204 No Content", async () => {
    stubFetch(new Response(null, { status: 204 }));

    await expect(apiFetch("/api/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("throws ApiError carrying the status and a string detail", async () => {
    stubFetch(jsonResponse({ detail: "invalid credentials" }, 401));

    const error = await apiFetch("/api/auth/login", { method: "POST" }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
    expect((error as ApiError).detail).toBe("invalid credentials");
    expect((error as ApiError).message).toBe("invalid credentials");
  });

  it("keeps a structured 422 detail intact", async () => {
    const detail = { errors: [{ row: 4, column: "spend", message: "not a number" }], warnings: [] };
    stubFetch(jsonResponse({ detail }, 422));

    const error = (await apiFetch("/api/uploads", { method: "POST" }).catch((e: unknown) => e)) as ApiError;

    expect(error.status).toBe(422);
    expect(error.detail).toEqual(detail);
  });

  it("survives a non-JSON error body", async () => {
    stubFetch(new Response("<html>502</html>", { status: 502 }));

    const error = (await apiFetch("/api/reports/latest").catch((e: unknown) => e)) as ApiError;

    expect(error.status).toBe(502);
    expect(error.message).toBe("Request failed with status 502");
  });
});

describe("extractIssues", () => {
  it("passes through the expected 422 shape", () => {
    const detail = {
      errors: [{ row: 4, column: "spend", message: "not a number" }],
      warnings: [{ row: 9, column: null, message: "duplicate row" }],
    };

    expect(extractIssues(detail)).toEqual(detail);
  });

  it("wraps a plain string detail as a single file-level error", () => {
    expect(extractIssues("file is empty")).toEqual({
      errors: [{ row: null, column: null, message: "file is empty" }],
      warnings: [],
    });
  });

  it("degrades to empty lists for anything else", () => {
    expect(extractIssues(null)).toEqual({ errors: [], warnings: [] });
    expect(extractIssues({ nonsense: 1 })).toEqual({ errors: [], warnings: [] });
  });
});
```

- [ ] **Step 7: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/lib/api.test.ts`
Expected: FAIL — `Failed to resolve import "./api"`.

- [ ] **Step 8: Write `api.ts`**

`frontend/src/lib/api.ts`:
```ts
import type { RowIssue, ValidationReport } from "./types";

/** Thrown for every non-2xx answer. `detail` is FastAPI's `detail` field, whatever shape it has. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" && detail.length > 0 ? detail : `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Browser-side API client. Paths are relative ("/api/..."), so the Next.js
 * rewrite keeps the auth cookies first-party (docs/PLAN.md §1 #8).
 * Never pass a client_id — the backend reads the tenant from the cookie.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  // FormData must keep its browser-generated multipart boundary, so only JSON strings get a type.
  if (typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...init, headers, credentials: "include" });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let body: unknown = null;
  if (text.length > 0) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const detail =
      body !== null && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ApiError(response.status, detail);
  }

  return body as T;
}

/**
 * Normalise whatever the upload endpoint put in `detail` into a ValidationReport
 * the UI can table up. Stage 3 is expected to send
 * {"detail": {"errors": [...], "warnings": [...]}}; anything else degrades safely.
 */
export function extractIssues(detail: unknown): ValidationReport {
  if (detail !== null && typeof detail === "object") {
    const candidate = detail as { errors?: unknown; warnings?: unknown };
    return {
      errors: Array.isArray(candidate.errors) ? (candidate.errors as RowIssue[]) : [],
      warnings: Array.isArray(candidate.warnings) ? (candidate.warnings as RowIssue[]) : [],
    };
  }
  if (typeof detail === "string" && detail.length > 0) {
    return { errors: [{ row: null, column: null, message: detail }], warnings: [] };
  }
  return { errors: [], warnings: [] };
}
```

- [ ] **Step 9: Run the whole suite**

Run: `cd /d/ad-optimizer-project/frontend && npm test`
Expected: `Test Files  2 passed (2)`, `Tests  20 passed (20)`.

- [ ] **Step 10: Typecheck and commit**

```bash
cd /d/ad-optimizer-project/frontend
npx tsc --noEmit && npm run lint
```
Expected: no output.
```bash
cd /d/ad-optimizer-project
git add frontend/src/lib
git commit -m "feat(frontend): API client, PKR formatting and backend type mirrors"
```

---

### Task 4: UI primitives and the `/login` + `/signup` pages

**Files:**
- Create: `frontend/src/components/ui/Button.tsx`
- Create: `frontend/src/components/ui/Field.tsx`
- Create: `frontend/src/components/auth/AuthForm.tsx`
- Create: `frontend/src/app/(auth)/login/page.tsx`
- Create: `frontend/src/app/(auth)/signup/page.tsx`
- Test: `frontend/src/components/auth/AuthForm.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError` (Task 3); `MeOut` (Task 3).
- Produces:
  ```tsx
  Button(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" })
  Field(props: { label: string; name: string; type?: string; required?: boolean; autoComplete?: string; minLength?: number })
  AuthForm(props: { mode: "login" | "signup" })   // "use client"
  ```
  Routes `/login` and `/signup`. Both post to `/api/auth/${mode}` and, on success, `router.push("/dashboard")` then `router.refresh()`.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/auth/AuthForm.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AuthForm from "./AuthForm";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const meOut = {
  user: { id: 1, email: "owner@shop.pk", role: "client", created_at: "2026-09-16T00:00:00Z" },
  client: { id: 1, business_name: "Shop", base_fee: "15000.00", performance_fee_pct: "20.00" },
};

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
});

describe("AuthForm", () => {
  it("shows only email and password in login mode", () => {
    render(<AuthForm mode="login" />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.queryByLabelText("Business name")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  });

  it("asks for a business name in signup mode", () => {
    render(<AuthForm mode="signup" />);

    expect(screen.getByLabelText("Business name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("posts the login payload and goes to the dashboard", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(meOut));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AuthForm mode="login" />);

    await user.type(screen.getByLabelText("Email"), "owner@shop.pk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/login", expect.objectContaining({ method: "POST" }));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      email: "owner@shop.pk",
      password: "correct-horse",
    });
    expect(refresh).toHaveBeenCalled();
  });

  it("includes the business name in the signup payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(meOut, 201));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AuthForm mode="signup" />);

    await user.type(screen.getByLabelText("Business name"), "Kolachi Kitchen");
    await user.type(screen.getByLabelText("Email"), "owner@shop.pk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      email: "owner@shop.pk",
      password: "correct-horse",
      business_name: "Kolachi Kitchen",
    });
  });

  it("shows the backend detail on a 401 and stays put", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid credentials" }, 401)));
    const user = userEvent.setup();
    render(<AuthForm mode="login" />);

    await user.type(screen.getByLabelText("Email"), "owner@shop.pk");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("invalid credentials");
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a friendly message when the email is taken", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "email already registered" }, 409)));
    const user = userEvent.setup();
    render(<AuthForm mode="signup" />);

    await user.type(screen.getByLabelText("Business name"), "Shop");
    await user.type(screen.getByLabelText("Email"), "taken@shop.pk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("email already registered");
  });
});
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/auth/AuthForm.test.tsx`
Expected: FAIL — `Failed to resolve import "./AuthForm"`.

- [ ] **Step 3: Write the two UI primitives**

`frontend/src/components/ui/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" };

/** transition-colors is the only hover effect allowed anywhere in the product. */
export default function Button({ variant = "primary", className = "", ...rest }: Props) {
  const base =
    "inline-flex items-center justify-center rounded-sm px-5 py-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const look =
    variant === "primary"
      ? "bg-teal text-ink hover:bg-teal/85"
      : "border border-slate/40 text-paper hover:border-slate";
  return <button className={`${base} ${look} ${className}`} {...rest} />;
}
```

`frontend/src/components/ui/Field.tsx`:
```tsx
type Props = {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  autoComplete?: string;
  minLength?: number;
};

/** Label and input are wired by id so getByLabelText finds the control. */
export default function Field({ label, name, type = "text", required = true, autoComplete, minLength }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs uppercase tracking-[0.18em] text-slate" htmlFor={name}>
        {label}
      </label>
      <input
        className="rounded-sm border border-slate/30 bg-surface px-4 py-3 text-paper outline-none transition-colors focus:border-teal"
        id={name}
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
        minLength={minLength}
      />
    </div>
  );
}
```

- [ ] **Step 4: Write `AuthForm.tsx`**

`frontend/src/components/auth/AuthForm.tsx`:
```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { ApiError, apiFetch } from "@/lib/api";
import type { MeOut } from "@/lib/types";

type Props = { mode: "login" | "signup" };

export default function AuthForm({ mode }: Props) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isSignup = mode === "signup";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);

    const data = new FormData(event.currentTarget);
    const payload: Record<string, string> = {
      email: String(data.get("email") ?? ""),
      password: String(data.get("password") ?? ""),
    };
    if (isSignup) {
      payload.business_name = String(data.get("business_name") ?? "");
    }

    try {
      await apiFetch<MeOut>(`/api/auth/${mode}`, { method: "POST", body: JSON.stringify(payload) });
      router.push("/dashboard");
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(
          caught.status === 429
            ? "Too many attempts. Wait a minute and try again."
            : caught.message,
        );
      } else {
        setError("Could not reach the server. Check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="flex flex-col gap-6" onSubmit={onSubmit} noValidate>
      {isSignup ? <Field label="Business name" name="business_name" autoComplete="organization" /> : null}
      <Field label="Email" name="email" type="email" autoComplete="email" />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete={isSignup ? "new-password" : "current-password"}
        minLength={isSignup ? 8 : undefined}
      />
      {error ? (
        <p className="text-sm text-coral" role="alert">
          {error}
        </p>
      ) : null}
      <Button disabled={busy} type="submit">
        {isSignup ? "Create account" : "Log in"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 5: Run the test**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/auth/AuthForm.test.tsx`
Expected: `Tests  6 passed (6)`.

- [ ] **Step 6: Write the two pages**

`frontend/src/app/(auth)/login/page.tsx`:
```tsx
import Link from "next/link";

import AuthForm from "@/components/auth/AuthForm";

export const metadata = { title: "Log in · Ad Spend Optimization" };

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-10 px-6 py-16">
      <div className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-slate">Ad Spend Optimization</p>
        <h1 className="font-display text-4xl leading-tight">Welcome back.</h1>
      </div>
      <AuthForm mode="login" />
      <p className="text-sm text-slate">
        No account yet?{" "}
        <Link className="text-teal underline underline-offset-4" href="/signup">
          Create one
        </Link>
      </p>
    </main>
  );
}
```

`frontend/src/app/(auth)/signup/page.tsx`:
```tsx
import Link from "next/link";

import AuthForm from "@/components/auth/AuthForm";

export const metadata = { title: "Sign up · Ad Spend Optimization" };

export default function SignupPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-10 px-6 py-16">
      <div className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-slate">Ad Spend Optimization</p>
        <h1 className="font-display text-4xl leading-tight">Find the leak in your ad spend.</h1>
        <p className="text-slate">Upload one export. We tell you which segments are burning money.</p>
      </div>
      <AuthForm mode="signup" />
      <p className="text-sm text-slate">
        Already have an account?{" "}
        <Link className="text-teal underline underline-offset-4" href="/login">
          Log in
        </Link>
      </p>
    </main>
  );
}
```

- [ ] **Step 7: Full check and commit**

```bash
cd /d/ad-optimizer-project/frontend
npm test && npx tsc --noEmit && npm run lint && npm run build
```
Expected: all tests pass; the build's route table now lists `/login` and `/signup`.
```bash
cd /d/ad-optimizer-project
git add frontend/src/app frontend/src/components
git commit -m "feat(frontend): login and signup pages with shared auth form"
```

---

### Task 5: Dashboard shell — server auth guard, nav, logout

**Files:**
- Create: `frontend/src/lib/server-api.ts`
- Create: `frontend/src/components/shell/DashboardNav.tsx`
- Create: `frontend/src/components/shell/LogoutButton.tsx`
- Create: `frontend/src/app/dashboard/layout.tsx`
- Create: `frontend/src/app/dashboard/page.tsx` (placeholder; Task 12 fills it in)
- Test: `frontend/src/lib/server-api.test.ts`
- Test: `frontend/src/components/shell/LogoutButton.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` (Task 3); `MeOut`, `ReportOut`, `UploadOut` (Task 3).
- Produces:
  ```ts
  // src/lib/server-api.ts  — server components only, never imported by a "use client" file
  backendUrl(): string                                        // process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  cookieHeader(all: { name: string; value: string }[]): string
  serverFetch<T>(path: string): Promise<{ status: number; data: T | null }>
  getMe(): Promise<MeOut | null>                              // null on any non-2xx
  getLatestReport(): Promise<ReportOut | null>
  getReport(runId: string): Promise<ReportOut | null>
  getUploads(): Promise<UploadOut[]>
  ```
  ```tsx
  DashboardNav(props: { businessName: string })
  LogoutButton()   // "use client"
  ```
  Route `/dashboard` and every route under it is now behind the guard.

- [ ] **Step 1: Write the failing server-api test**

`frontend/src/lib/server-api.test.ts`:
```ts
import { describe, expect, it, vi } from "vitest";

import { cookieHeader, getLatestReport, getMe, getUploads } from "./server-api";

vi.mock("next/headers", () => ({
  cookies: async () => ({
    getAll: () => [
      { name: "access_token", value: "header.payload.signature" },
      { name: "refresh_token", value: "r.e.f" },
    ],
  }),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const meOut = {
  user: { id: 1, email: "owner@shop.pk", role: "client", created_at: "2026-09-16T00:00:00Z" },
  client: { id: 1, business_name: "Kolachi Kitchen", base_fee: "15000.00", performance_fee_pct: "20.00" },
};

describe("cookieHeader", () => {
  it("rebuilds a Cookie header from the request cookies", () => {
    expect(cookieHeader([{ name: "access_token", value: "a.b.c" }, { name: "x", value: "1" }])).toBe(
      "access_token=a.b.c; x=1",
    );
  });

  it("is empty when there are no cookies", () => {
    expect(cookieHeader([])).toBe("");
  });
});

describe("getMe", () => {
  it("calls the backend directly with the forwarded cookies", async () => {
    vi.stubEnv("BACKEND_URL", "http://backend.test");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(meOut));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getMe()).resolves.toEqual(meOut);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/api/auth/me",
      expect.objectContaining({
        cache: "no-store",
        headers: { cookie: "access_token=header.payload.signature; refresh_token=r.e.f" },
      }),
    );
  });

  it("is null on 401 so the layout can redirect", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "not authenticated" }, 401)));

    await expect(getMe()).resolves.toBeNull();
  });
});

describe("getLatestReport", () => {
  it("returns the report on 200", async () => {
    const report = { run_id: 3, total_spend: 400000, headline_waste: 100000 };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(report)));

    await expect(getLatestReport()).resolves.toMatchObject({ run_id: 3 });
  });

  it("is null when there is nothing approved yet (404, 204 or a null body)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "not found" }, 404)));
    await expect(getLatestReport()).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(getLatestReport()).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(null)));
    await expect(getLatestReport()).resolves.toBeNull();
  });
});

describe("getUploads", () => {
  it("returns an empty list rather than throwing when the call fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "nope" }, 500)));

    await expect(getUploads()).resolves.toEqual([]);
  });
});
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/lib/server-api.test.ts`
Expected: FAIL — `Failed to resolve import "./server-api"`.

- [ ] **Step 3: Write `server-api.ts`**

`frontend/src/lib/server-api.ts`:
```ts
import { cookies } from "next/headers";

import type { MeOut, ReportOut, UploadOut } from "./types";

/**
 * Server components talk to FastAPI directly — the Next rewrite only exists for
 * the browser. Read the env var per call so tests can stub it.
 */
export function backendUrl(): string {
  return process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
}

/** Rebuild a Cookie header from the incoming request's cookies. */
export function cookieHeader(all: { name: string; value: string }[]): string {
  return all.map((cookie) => `${cookie.name}=${encodeURIComponent(cookie.value)}`).join("; ");
}

/**
 * One cookie-forwarding fetch. Returns the status as well as the body so callers
 * can tell "not logged in" (401) from "nothing approved yet" (404/204).
 */
export async function serverFetch<T>(path: string): Promise<{ status: number; data: T | null }> {
  const store = await cookies();
  const response = await fetch(`${backendUrl()}${path}`, {
    headers: { cookie: cookieHeader(store.getAll()) },
    cache: "no-store",
  });

  if (response.status === 204) {
    return { status: 204, data: null };
  }

  const text = await response.text();
  let data: T | null = null;
  if (text.length > 0) {
    try {
      data = JSON.parse(text) as T;
    } catch {
      data = null;
    }
  }
  return { status: response.status, data };
}

/** null means "send them to /login" — including when the backend is down. */
export async function getMe(): Promise<MeOut | null> {
  const { status, data } = await serverFetch<MeOut>("/api/auth/me");
  return status === 200 ? data : null;
}

export async function getLatestReport(): Promise<ReportOut | null> {
  const { status, data } = await serverFetch<ReportOut>("/api/reports/latest");
  return status === 200 ? data : null;
}

export async function getReport(runId: string): Promise<ReportOut | null> {
  const { status, data } = await serverFetch<ReportOut>(`/api/reports/${encodeURIComponent(runId)}`);
  return status === 200 ? data : null;
}

export async function getUploads(): Promise<UploadOut[]> {
  const { status, data } = await serverFetch<UploadOut[]>("/api/uploads");
  return status === 200 && Array.isArray(data) ? data : [];
}
```

- [ ] **Step 4: Run the test**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/lib/server-api.test.ts`
Expected: `Tests  7 passed (7)`.

- [ ] **Step 5: Write the failing logout test**

`frontend/src/components/shell/LogoutButton.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import LogoutButton from "./LogoutButton";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

describe("LogoutButton", () => {
  it("clears the session and goes to /login", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<LogoutButton />);

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", expect.objectContaining({ method: "POST" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
  });

  it("still leaves for /login if the logout call fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const user = userEvent.setup();
    render(<LogoutButton />);

    await user.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
  });
});
```

- [ ] **Step 6: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/shell/LogoutButton.test.tsx`
Expected: FAIL — `Failed to resolve import "./LogoutButton"`.

- [ ] **Step 7: Write the nav and the logout button**

`frontend/src/components/shell/LogoutButton.tsx`:
```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiFetch } from "@/lib/api";

export default function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    try {
      await apiFetch<void>("/api/auth/logout", { method: "POST" });
    } catch {
      // The cookie may already be gone. Leave anyway — the guard will sort it out.
    }
    router.push("/login");
    router.refresh();
  }

  return (
    <button
      className="text-sm text-slate transition-colors hover:text-paper disabled:opacity-50"
      disabled={busy}
      onClick={logout}
      type="button"
    >
      Log out
    </button>
  );
}
```

`frontend/src/components/shell/DashboardNav.tsx`:
```tsx
import Link from "next/link";

import LogoutButton from "./LogoutButton";

/** Stage 7 adds a /dashboard/billing link here. */
export default function DashboardNav({ businessName }: { businessName: string }) {
  return (
    <header className="border-b border-slate/20">
      <nav className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-5 sm:px-6">
        <Link className="font-display text-base" href="/dashboard">
          {businessName}
        </Link>
        <div className="flex items-center gap-6 text-sm">
          <Link className="text-slate transition-colors hover:text-paper" href="/dashboard">
            Report
          </Link>
          <Link className="text-slate transition-colors hover:text-paper" href="/dashboard/upload">
            Upload
          </Link>
        </div>
        <div className="ml-auto">
          <LogoutButton />
        </div>
      </nav>
    </header>
  );
}
```

- [ ] **Step 8: Write the guard layout**

`frontend/src/app/dashboard/layout.tsx`:
```tsx
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import DashboardNav from "@/components/shell/DashboardNav";
import { getMe } from "@/lib/server-api";

/**
 * The auth guard for /dashboard/*. It forwards the request cookies to
 * GET /api/auth/me and sends anyone without a valid session to /login.
 * Calling cookies() already opts this subtree out of static rendering.
 */
export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const me = await getMe();
  if (me === null) {
    redirect("/login");
  }

  return (
    <div className="min-h-screen">
      <DashboardNav businessName={me.client?.business_name ?? me.user.email} />
      <main className="mx-auto w-full max-w-6xl px-4 pb-24 pt-10 sm:px-6">{children}</main>
    </div>
  );
}
```

`frontend/src/app/dashboard/page.tsx` — a placeholder so the route exists; **Task 12 replaces it**:
```tsx
export default function DashboardPage() {
  return <p className="text-slate">The report lands here in Task 12.</p>;
}
```

- [ ] **Step 9: Run the tests, then check the guard by hand**

Run: `cd /d/ad-optimizer-project/frontend && npm test`
Expected: `Test Files  5 passed (5)`, `Tests  35 passed (35)` — format 10, api 10, server-api 7, AuthForm 6, LogoutButton 2.

Start the backend (`cd /d/ad-optimizer-project/backend && .venv/Scripts/uvicorn app.main:app --port 8000`) and the frontend (`npm run dev`), then open http://localhost:3000/dashboard in a private window.
Expected: an immediate redirect to `/login`. Log in with a client created via `/signup`; you land on `/dashboard` with the business name in the nav. Click **Log out** → back at `/login`, and `/dashboard` redirects again. Stop both servers.

- [ ] **Step 10: Commit**

```bash
cd /d/ad-optimizer-project/frontend
npx tsc --noEmit && npm run lint
cd /d/ad-optimizer-project
git add frontend/src
git commit -m "feat(frontend): dashboard shell with server-side auth guard and logout"
```

---

### Task 6: Upload page — drop zone, row-level errors, analysis polling

**Files:**
- Create: `frontend/src/components/upload/IssueTable.tsx`
- Create: `frontend/src/components/upload/UploadPanel.tsx`
- Create: `frontend/src/app/dashboard/upload/page.tsx`
- Test: `frontend/src/components/upload/UploadPanel.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError`, `extractIssues` (Task 3); `UploadOut`, `RunOut`, `RowIssue`, `ValidationReport` (Task 3); `Button` (Task 4).
- Produces:
  ```tsx
  IssueTable(props: { title: string; issues: RowIssue[]; tone: "error" | "warning" })
  UploadPanel()   // "use client"
  ```
  Route `/dashboard/upload`. Flow: pick or drop a `.csv` → `POST /api/uploads` (multipart field name **`file`**) → show issues → **Analyze** → `POST /api/analyze/{uploadId}` → poll `GET /api/runs/{id}` every **2000 ms** until `status` is `done` or `failed`.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/upload/UploadPanel.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import UploadPanel from "./UploadPanel";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function csvFile(name = "ads.csv"): File {
  return new File(["date,campaign_id,placement\n2026-09-01,c1,feed\n"], name, { type: "text/csv" });
}

const validatedUpload = {
  id: 12,
  uploaded_at: "2026-09-16T09:00:00Z",
  original_filename: "ads.csv",
  row_count: 900,
  date_range_start: "2026-08-01",
  date_range_end: "2026-08-31",
  status: "validated",
  validation_report: { errors: [], warnings: [] },
};

const queuedRun = {
  id: 5,
  upload_id: 12,
  status: "queued",
  review_status: "pending",
  headline_waste: null,
  error_message: null,
  created_at: "2026-09-16T09:00:05Z",
};

afterEach(() => {
  vi.useRealTimers();
});

describe("UploadPanel", () => {
  it("uploads a chosen file as multipart with the field name 'file'", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(validatedUpload, 201));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/uploads", expect.anything()));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const body = init.body as FormData;
    expect(init.method).toBe("POST");
    expect((body.get("file") as File).name).toBe("ads.csv");
    expect(await screen.findByText(/900 rows/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled();
  });

  it("refuses a non-CSV file before calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(
      screen.getByLabelText("Choose a CSV file"),
      new File(["%PDF"], "report.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload a .csv file");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("tables the row-level errors from a 422 body and offers no Analyze button", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: {
              errors: [
                { row: 4, column: "spend", message: "not a number: 'abc'" },
                { row: 9, column: "clicks", message: "clicks (50) exceed impressions (10)" },
              ],
              warnings: [{ row: 11, column: "conversions", message: "conversions exceed clicks" }],
            },
          },
          422,
        ),
      ),
    );
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    expect(await screen.findByText("not a number: 'abc'")).toBeInTheDocument();
    expect(screen.getByText("clicks (50) exceed impressions (10)")).toBeInTheDocument();
    expect(screen.getByText("conversions exceed clicks")).toBeInTheDocument();
    expect(screen.getByText("Row 4")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyze" })).not.toBeInTheDocument();
  });

  it("tables the errors when the API accepts the file but marks it failed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            ...validatedUpload,
            status: "failed",
            validation_report: {
              errors: [{ row: null, column: "revenue", message: "missing column" }],
              warnings: [],
            },
          },
          201,
        ),
      ),
    );
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    expect(await screen.findByText("missing column")).toBeInTheDocument();
    expect(screen.getByText("Whole file")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyze" })).not.toBeInTheDocument();
  });

  it("explains a duplicate upload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "this file was already uploaded" }, 409)),
    );
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    expect(await screen.findByRole("alert")).toHaveTextContent("this file was already uploaded");
  });

  it("starts a run, polls every 2 seconds, and stops at 'awaiting admin review'", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(validatedUpload, 201))
      .mockResolvedValueOnce(jsonResponse(queuedRun, 202))
      .mockResolvedValueOnce(jsonResponse({ ...queuedRun, status: "running" }))
      .mockResolvedValue(
        jsonResponse({ ...queuedRun, status: "done", review_status: "pending", headline_waste: 100000 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    await vi.waitFor(() => expect(screen.getByText(/Queued/)).toBeInTheDocument());

    await vi.advanceTimersByTimeAsync(2000);
    await vi.waitFor(() => expect(screen.getByText(/Running/)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith("/api/runs/5", expect.anything());

    await vi.advanceTimersByTimeAsync(2000);
    await vi.waitFor(() => expect(screen.getByText(/awaiting admin review/i)).toBeInTheDocument());

    const callsAfterDone = fetchMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(6000);
    expect(fetchMock.mock.calls.length).toBe(callsAfterDone);
  });

  it("links to the report when the run comes back already approved", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(validatedUpload, 201))
        .mockResolvedValueOnce(jsonResponse(queuedRun, 202))
        .mockResolvedValue(
          jsonResponse({ ...queuedRun, status: "done", review_status: "approved", headline_waste: 100000 }),
        ),
    );
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    await vi.advanceTimersByTimeAsync(2000);

    const link = await vi.waitFor(() => screen.getByRole("link", { name: "See the report" }));
    expect(link).toHaveAttribute("href", "/dashboard/reports/5");
  });

  it("shows the backend error message when the run fails", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(validatedUpload, 201))
        .mockResolvedValueOnce(jsonResponse(queuedRun, 202))
        .mockResolvedValue(
          jsonResponse({ ...queuedRun, status: "failed", error_message: "no significant segments" }),
        ),
    );
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    await vi.advanceTimersByTimeAsync(2000);

    await vi.waitFor(() => expect(screen.getByText("no significant segments")).toBeInTheDocument());
  });

  it("accepts a file dropped on the drop zone", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(validatedUpload, 201));
    vi.stubGlobal("fetch", fetchMock);
    render(<UploadPanel />);

    fireEvent.drop(screen.getByTestId("drop-zone"), {
      dataTransfer: { files: [csvFile("dropped.csv")], types: ["Files"] },
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    expect((body.get("file") as File).name).toBe("dropped.csv");
  });
});
```

Two real gotchas are baked into this test: `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })` is mandatory whenever fake timers are on, or every `user.*` call hangs forever; and `vi.waitFor` (not React Testing Library's `waitFor`) is the one that cooperates with fake timers.

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/upload/UploadPanel.test.tsx`
Expected: FAIL — `Failed to resolve import "./UploadPanel"`.

- [ ] **Step 3: Write `IssueTable.tsx`**

`frontend/src/components/upload/IssueTable.tsx`:
```tsx
import type { RowIssue } from "@/lib/types";

type Props = { title: string; issues: RowIssue[]; tone: "error" | "warning" };

/** Hairline dividers, no cell borders — the house table style. */
export default function IssueTable({ title, issues, tone }: Props) {
  if (issues.length === 0) return null;

  return (
    <section className="mt-10">
      <h3 className={`font-display text-lg ${tone === "error" ? "text-coral" : "text-paper"}`}>
        {title} <span className="text-slate">({issues.length})</span>
      </h3>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[30rem] text-sm">
          <thead>
            <tr className="border-b border-slate/20 text-left text-xs uppercase tracking-[0.14em] text-slate">
              <th className="w-28 py-3 pr-4 font-normal" scope="col">
                Where
              </th>
              <th className="w-40 py-3 pr-4 font-normal" scope="col">
                Column
              </th>
              <th className="py-3 font-normal" scope="col">
                Problem
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate/20">
            {issues.map((issue, index) => (
              <tr
                className={tone === "error" ? "text-coral" : "text-slate"}
                key={`${issue.row}-${issue.column}-${index}`}
              >
                <td className="py-3 pr-4 tabular-nums">
                  {issue.row === null ? "Whole file" : `Row ${issue.row}`}
                </td>
                <td className="py-3 pr-4">{issue.column ?? "—"}</td>
                <td className="py-3 text-paper">{issue.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Write `UploadPanel.tsx`**

`frontend/src/components/upload/UploadPanel.tsx`:
```tsx
"use client";

import Link from "next/link";
import { useEffect, useState, type DragEvent } from "react";

import Button from "@/components/ui/Button";
import IssueTable from "@/components/upload/IssueTable";
import { ApiError, apiFetch, extractIssues } from "@/lib/api";
import type { RunOut, UploadOut, ValidationReport } from "@/lib/types";

const POLL_MS = 2000;

const RUN_LABELS: Record<RunOut["status"], string> = {
  queued: "Queued — waiting to start.",
  running: "Running — crunching your segments.",
  done: "Done.",
  failed: "Failed.",
};

export default function UploadPanel() {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadOut | null>(null);
  const [issues, setIssues] = useState<ValidationReport>({ errors: [], warnings: [] });
  const [run, setRun] = useState<RunOut | null>(null);

  const runId = run?.id;
  const runStatus = run?.status;

  // Poll the run until it settles. Re-armed whenever the status changes, torn
  // down on unmount, and never armed again once the run is done or failed.
  useEffect(() => {
    if (runId === undefined || runStatus === "done" || runStatus === "failed") return;

    const timer = setInterval(() => {
      apiFetch<RunOut>(`/api/runs/${runId}`)
        .then(setRun)
        .catch(() => {
          clearInterval(timer);
          setError("Lost contact with the server while the analysis was running. Reload to check again.");
        });
    }, POLL_MS);

    return () => clearInterval(timer);
  }, [runId, runStatus]);

  async function send(file: File) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Upload a .csv file — that is what the ad platforms export.");
      return;
    }

    setBusy(true);
    setError(null);
    setUpload(null);
    setRun(null);
    setIssues({ errors: [], warnings: [] });

    const form = new FormData();
    form.append("file", file);

    try {
      const result = await apiFetch<UploadOut>("/api/uploads", { method: "POST", body: form });
      setUpload(result);
      setIssues(result.validation_report ?? { errors: [], warnings: [] });
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 422) {
        setIssues(extractIssues(caught.detail));
      } else if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError("Could not reach the server. Check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function analyze() {
    if (upload === null) return;
    setError(null);
    try {
      setRun(await apiFetch<RunOut>(`/api/analyze/${upload.id}`, { method: "POST" }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not start the analysis.");
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) void send(file);
  }

  const canAnalyze = upload !== null && upload.status !== "failed" && issues.errors.length === 0;

  return (
    <div className="max-w-3xl">
      <h1 className="font-display text-4xl leading-tight">Upload an export.</h1>
      <p className="mt-3 max-w-xl text-slate">
        One CSV of your daily rows. Breakdowns your platform cannot export together may be left blank — each
        dimension is analysed only on the rows that carry it.{" "}
        <a className="text-teal underline underline-offset-4" href="/api/uploads/template.csv">
          Download the template
        </a>
        .
      </p>

      <div
        className={`mt-10 flex flex-col items-center gap-4 rounded-sm border border-dashed px-6 py-16 text-center transition-colors ${
          dragging ? "border-teal bg-surface" : "border-slate/40"
        }`}
        data-testid="drop-zone"
        onDragLeave={() => setDragging(false)}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDrop={onDrop}
      >
        <p className="text-slate">Drag your CSV here</p>
        <label className="cursor-pointer text-sm text-teal underline underline-offset-4" htmlFor="csv-input">
          Choose a CSV file
        </label>
        <input
          accept=".csv,text/csv"
          className="sr-only"
          id="csv-input"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void send(file);
            event.target.value = "";
          }}
          type="file"
        />
      </div>

      {busy ? <p className="mt-6 text-slate">Uploading and validating…</p> : null}

      {error ? (
        <p className="mt-6 text-coral" role="alert">
          {error}
        </p>
      ) : null}

      {upload !== null && upload.status !== "failed" ? (
        <p className="mt-8 text-paper">
          <span className="font-display text-2xl">{upload.original_filename}</span>{" "}
          <span className="text-slate">
            — {upload.row_count ?? 0} rows
            {upload.date_range_start && upload.date_range_end
              ? `, ${upload.date_range_start} to ${upload.date_range_end}`
              : ""}
          </span>
        </p>
      ) : null}

      <IssueTable issues={issues.errors} title="Rows we could not read" tone="error" />
      <IssueTable issues={issues.warnings} title="Worth a look" tone="warning" />

      {canAnalyze && run === null ? (
        <div className="mt-10">
          <Button onClick={analyze} type="button">
            Analyze
          </Button>
        </div>
      ) : null}

      {run !== null ? (
        <div className="mt-10 border-t border-slate/20 pt-6">
          <p className="text-paper">{RUN_LABELS[run.status]}</p>
          {run.status === "failed" && run.error_message ? (
            <p className="mt-2 text-coral">{run.error_message}</p>
          ) : null}
          {run.status === "done" && run.review_status !== "approved" ? (
            <p className="mt-2 max-w-xl text-slate">
              Your numbers are in and awaiting admin review. We check every run before it reaches you — the
              report appears on your dashboard as soon as it is approved.
            </p>
          ) : null}
          {run.status === "done" && run.review_status === "approved" ? (
            <Link
              className="mt-3 inline-block text-teal underline underline-offset-4"
              href={`/dashboard/reports/${run.id}`}
            >
              See the report
            </Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Run the test**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/upload/UploadPanel.test.tsx`
Expected: `Tests  9 passed (9)`.

- [ ] **Step 6: Write the page**

`frontend/src/app/dashboard/upload/page.tsx`:
```tsx
import UploadPanel from "@/components/upload/UploadPanel";

export const metadata = { title: "Upload · Ad Spend Optimization" };

export default function UploadPage() {
  return <UploadPanel />;
}
```

- [ ] **Step 7: Full check and commit**

```bash
cd /d/ad-optimizer-project/frontend
npm test && npx tsc --noEmit && npm run lint
```
Expected: every test file passes; no other output.
```bash
cd /d/ad-optimizer-project
git add frontend/src
git commit -m "feat(frontend): upload page with row-level validation errors and run polling"
```

---

### Task 7: `FlowStatic` — the SVG hero and reduced-motion fallback

A left "budget" source, a teal band flowing right into a "working spend" node, and a coral band whose **thickness is proportional to `headline_waste / total_spend`** peeling downward into a "wasted" node. Every node carries its real rupee figure. This is what `prefers-reduced-motion` visitors see, so it must carry the whole message on its own.

**Files:**
- Create: `frontend/src/lib/motion.ts`
- Create: `frontend/src/components/hero/FlowStatic.tsx`
- Test: `frontend/src/components/hero/FlowStatic.test.tsx`

**Interfaces:**
- Consumes: `formatPKR`, `formatPct`, `wasteShare` (Task 3).
- Produces:
  ```ts
  // src/lib/motion.ts
  const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
  const HERO_DURATION_MS = 4000;
  const HERO_COLORS = { teal: "#2dd4bf", coral: "#ff6b4a", slate: "#8891a5" };
  useReducedMotion(): boolean         // "use client"; true until the browser answers
  ```
  ```tsx
  const BAND = 140;                                    // exported from FlowStatic.tsx
  FlowStatic(props: { totalSpend: number; headlineWaste: number })
  ```
  Band geometry, shared with `FlowParticles`: inside a `0 0 800 420` viewBox the two bands total `BAND = 140` units; coral is `max(3, round(BAND * share))` and teal is `max(3, BAND - coral)`.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/hero/FlowStatic.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import FlowStatic from "./FlowStatic";

describe("FlowStatic", () => {
  it("labels the budget, working spend and waste with real rupee figures", () => {
    render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    expect(screen.getByText("Rs. 400,000")).toBeInTheDocument();
    expect(screen.getByText("Rs. 100,000")).toBeInTheDocument();
    expect(screen.getByText("Rs. 300,000")).toBeInTheDocument();
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("Working spend")).toBeInTheDocument();
    expect(screen.getByText("Wasted")).toBeInTheDocument();
  });

  it("is an accessible image with the share spelled out", () => {
    render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Of Rs. 400,000 spent, Rs. 100,000 — 25.0% — is estimated waste.",
    );
  });

  it("scales the coral band thickness to the waste share", () => {
    render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    // BAND = 140 units; a 25% share means 35 coral against 105 teal.
    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "35");
    expect(screen.getByTestId("working-band")).toHaveAttribute("stroke-width", "105");
  });

  it("keeps a hairline coral band visible when almost nothing is wasted", () => {
    render(<FlowStatic headlineWaste={100} totalSpend={400000} />);

    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "3");
  });

  it("degrades to a zero-waste diagram when there is no spend", () => {
    render(<FlowStatic headlineWaste={0} totalSpend={0} />);

    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "3");
    expect(screen.getByTestId("working-band")).toHaveAttribute("stroke-width", "137");
    expect(screen.getAllByText("Rs. 0").length).toBeGreaterThan(0);
  });

  it("contains no animation at all — this is the reduced-motion fallback", () => {
    const { container } = render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    expect(container.querySelector("animate")).toBeNull();
    expect(container.querySelector("animateTransform")).toBeNull();
    expect(container.innerHTML).not.toContain("animate-");
    expect(container.innerHTML).not.toContain("transition");
  });
});
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/hero/FlowStatic.test.tsx`
Expected: FAIL — `Failed to resolve import "./FlowStatic"`.

- [ ] **Step 3: Write `motion.ts`**

`frontend/src/lib/motion.ts`:
```ts
"use client";

import { useEffect, useState } from "react";

export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/** The single bold animation runs for exactly this long, once. The count-up is synced to it. */
export const HERO_DURATION_MS = 4000;

/**
 * The only place hex literals are allowed outside globals.css: SVG gradient
 * stops and Three.js colour buffers cannot read Tailwind utilities.
 * These MUST stay identical to the --color-* tokens in globals.css.
 */
export const HERO_COLORS = {
  teal: "#2dd4bf",
  coral: "#ff6b4a",
  slate: "#8891a5",
} as const;

/**
 * True until the browser says otherwise, so the server render and the first
 * paint are always the static hero — someone who asked for no motion never
 * catches a frame of it.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(true);

  useEffect(() => {
    const query = window.matchMedia(REDUCED_MOTION_QUERY);
    setReduced(query.matches);

    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
```

- [ ] **Step 4: Write `FlowStatic.tsx`**

`frontend/src/components/hero/FlowStatic.tsx`:
```tsx
import { formatPKR, formatPct, wasteShare } from "@/lib/format";
import { HERO_COLORS } from "@/lib/motion";

/** Combined thickness of the two bands, in viewBox units. FlowParticles splits the same way. */
export const BAND = 140;

type Props = { totalSpend: number; headlineWaste: number };

/**
 * The static hero, and the prefers-reduced-motion fallback — so it has to tell
 * the whole story by itself: how much went in, how much worked, how much leaked.
 * Deliberately free of <animate>, CSS transitions and hover effects.
 */
export default function FlowStatic({ totalSpend, headlineWaste }: Props) {
  const share = wasteShare(headlineWaste, totalSpend);
  const coralWidth = Math.max(3, Math.round(BAND * share));
  const workingWidth = Math.max(3, BAND - coralWidth);
  const working = Math.max(0, totalSpend - headlineWaste);

  return (
    <svg
      aria-label={`Of ${formatPKR(totalSpend)} spent, ${formatPKR(headlineWaste)} — ${formatPct(
        share * 100,
      )} — is estimated waste.`}
      className="h-full w-full"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      viewBox="0 0 800 420"
    >
      <defs>
        <linearGradient id="flow-working" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor={HERO_COLORS.teal} stopOpacity="0.35" />
          <stop offset="100%" stopColor={HERO_COLORS.teal} stopOpacity="0.9" />
        </linearGradient>
        <linearGradient id="flow-waste" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor={HERO_COLORS.coral} stopOpacity="0.25" />
          <stop offset="100%" stopColor={HERO_COLORS.coral} stopOpacity="0.95" />
        </linearGradient>
      </defs>

      {/* Budget source */}
      <rect fill="url(#flow-working)" height={BAND} rx="4" width="14" x="96" y="110" />
      <text fill={HERO_COLORS.slate} fontSize="15" letterSpacing="2" x="40" y="88">
        Budget
      </text>
      <text className="numeral" fill="currentColor" fontSize="30" x="40" y="286">
        {formatPKR(totalSpend)}
      </text>

      {/* Working spend: straight through to the conversions node */}
      <path
        d="M 110 180 C 300 180, 420 150, 620 150"
        data-testid="working-band"
        fill="none"
        stroke="url(#flow-working)"
        strokeLinecap="butt"
        strokeWidth={workingWidth}
      />

      {/* Waste: peels downward */}
      <path
        d="M 110 240 C 300 250, 380 300, 620 348"
        data-testid="waste-band"
        fill="none"
        stroke="url(#flow-waste)"
        strokeLinecap="butt"
        strokeWidth={coralWidth}
      />

      {/* Working-spend node */}
      <circle cx="640" cy="150" fill={HERO_COLORS.teal} r="9" />
      <text fill={HERO_COLORS.slate} fontSize="15" letterSpacing="2" x="662" y="140">
        Working spend
      </text>
      <text className="numeral" fill="currentColor" fontSize="24" x="662" y="172">
        {formatPKR(working)}
      </text>

      {/* Wasted node */}
      <circle cx="640" cy="348" fill={HERO_COLORS.coral} r="9" />
      <text fill={HERO_COLORS.coral} fontSize="15" letterSpacing="2" x="662" y="338">
        Wasted
      </text>
      <text className="numeral" fill={HERO_COLORS.coral} fontSize="24" x="662" y="370">
        {formatPKR(headlineWaste)}
      </text>
    </svg>
  );
}
```

- [ ] **Step 5: Run the test**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/hero/FlowStatic.test.tsx`
Expected: `Tests  6 passed (6)`.

- [ ] **Step 6: Look at it**

Temporarily replace `frontend/src/app/dashboard/page.tsx` with:
```tsx
import FlowStatic from "@/components/hero/FlowStatic";

export default function DashboardPage() {
  return (
    <div className="h-[420px]">
      <FlowStatic headlineWaste={100000} totalSpend={400000} />
    </div>
  );
}
```
Start the backend and `npm run dev`, log in, open http://localhost:3000/dashboard.
Expected: a teal band roughly three times thicker than the coral one, the coral band clearly peeling down to a coral dot labelled "Wasted / Rs. 100,000". Shrink the window to 400px — the SVG scales and nothing overflows. Then **restore `page.tsx` to the Task 5 placeholder**.

- [ ] **Step 7: Commit**

```bash
cd /d/ad-optimizer-project/frontend
npm test && npx tsc --noEmit && npm run lint
cd /d/ad-optimizer-project
git add frontend/src
git commit -m "feat(frontend): static SVG flow hero driven by the real waste share"
```

---

### Task 8: `FlowParticles` + `Hero` + `CountUp` — the one bold animation

**Files:**
- Create: `frontend/src/components/hero/FlowParticles.tsx`
- Create: `frontend/src/components/hero/Hero.tsx`
- Create: `frontend/src/components/dashboard/CountUp.tsx`
- Test: `frontend/src/components/hero/Hero.test.tsx`
- Test: `frontend/src/components/dashboard/CountUp.test.tsx`

**Interfaces:**
- Consumes: `FlowStatic` (Task 7); `useReducedMotion`, `HERO_DURATION_MS`, `HERO_COLORS` (Task 7); `wasteShare`, `formatPKR` (Task 3); `three`, `@react-three/fiber`, `@react-three/drei` (Task 2).
- Produces:
  ```tsx
  FlowParticles(props: { totalSpend: number; headlineWaste: number })   // "use client", never server-rendered
  Hero(props: { totalSpend: number; headlineWaste: number })            // "use client"
  CountUp(props: { value: number; animate: boolean; durationMs?: number; format?: (n: number) => string })
  ```

**Testing rule for this task:** jsdom has no WebGL. `FlowParticles` is **never rendered in a test** — `Hero.test.tsx` mocks the module by path, so the only thing under test is the branch `Hero` takes.

- [ ] **Step 1: Write the failing Hero test**

`frontend/src/components/hero/Hero.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Hero from "./Hero";

// jsdom cannot run WebGL. The particle stream is replaced by a marker so this
// test only exercises Hero's reduced-motion branch.
vi.mock("@/components/hero/FlowParticles", () => ({
  default: ({ headlineWaste }: { headlineWaste: number }) => (
    <div data-testid="flow-particles">{headlineWaste}</div>
  ),
}));

function setReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("Hero", () => {
  it("renders the static SVG when the visitor asked for reduced motion", async () => {
    setReducedMotion(true);

    render(<Hero headlineWaste={100000} totalSpend={400000} />);

    expect(await screen.findByRole("img")).toHaveAccessibleName(/Rs. 100,000/);
    expect(screen.queryByTestId("flow-particles")).not.toBeInTheDocument();
  });

  it("asks the browser with the prefers-reduced-motion query", () => {
    setReducedMotion(true);

    render(<Hero headlineWaste={100000} totalSpend={400000} />);

    expect(window.matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");
  });

  it("swaps in the particle stream when motion is allowed", async () => {
    setReducedMotion(false);

    render(<Hero headlineWaste={100000} totalSpend={400000} />);

    expect(await screen.findByTestId("flow-particles")).toHaveTextContent("100000");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the failing CountUp test**

`frontend/src/components/dashboard/CountUp.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CountUp from "./CountUp";

describe("CountUp", () => {
  it("renders the final figure immediately when animation is off", () => {
    render(<CountUp animate={false} value={100000} />);

    expect(screen.getByText("Rs. 100,000")).toBeInTheDocument();
  });

  it("starts at zero and lands exactly on the value when animating", async () => {
    render(<CountUp animate durationMs={40} value={100000} />);

    expect(screen.getByText("Rs. 0")).toBeInTheDocument();
    expect(await screen.findByText("Rs. 100,000")).toBeInTheDocument();
  });

  it("uses a caller-supplied formatter", () => {
    render(<CountUp animate={false} format={(n) => `${n} leaks`} value={7} />);

    expect(screen.getByText("7 leaks")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run both to watch them fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/hero/Hero.test.tsx src/components/dashboard/CountUp.test.tsx`
Expected: FAIL — `Failed to resolve import "./Hero"` and `Failed to resolve import "./CountUp"`.

- [ ] **Step 4: Write `CountUp.tsx`**

`frontend/src/components/dashboard/CountUp.tsx`:
```tsx
"use client";

import { useEffect, useState } from "react";

import { formatPKR } from "@/lib/format";
import { HERO_DURATION_MS } from "@/lib/motion";

type Props = {
  value: number;
  animate: boolean;
  durationMs?: number;
  format?: (n: number) => string;
};

/**
 * Counts up over the same window as the hero's coral drip, so the number and
 * the picture land together. `animate={false}` — reduced motion, or an admin
 * view — renders the final figure with no movement at all.
 */
export default function CountUp({
  value,
  animate,
  durationMs = HERO_DURATION_MS,
  format = formatPKR,
}: Props) {
  const [shown, setShown] = useState(animate ? 0 : value);

  useEffect(() => {
    if (!animate) {
      setShown(value);
      return;
    }

    let frame = 0;
    const start = performance.now();

    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic: quick, then settles
      setShown(value * eased); // eased === 1 on the last frame, so it lands exactly
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [animate, value, durationMs]);

  return <span>{format(shown)}</span>;
}
```

- [ ] **Step 5: Write `FlowParticles.tsx`**

`frontend/src/components/hero/FlowParticles.tsx`:
```tsx
"use client";

import { PointMaterial } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { wasteShare } from "@/lib/format";
import { HERO_COLORS, HERO_DURATION_MS } from "@/lib/motion";

const COUNT = 1400;
const DURATION = HERO_DURATION_MS / 1000;
const SPLIT = 0.52; // progress at which the wasteful particles start peeling away
const X_START = -4.4;
const X_END = 4.4;

type Props = { totalSpend: number; headlineWaste: number };

type Lanes = {
  phase: Float32Array; // 0..0.4 head start, so the stream has a leading edge
  laneY: Float32Array;
  drift: Float32Array;
  waste: Uint8Array;
};

function makeLanes(share: number): Lanes {
  const phase = new Float32Array(COUNT);
  const laneY = new Float32Array(COUNT);
  const drift = new Float32Array(COUNT);
  const waste = new Uint8Array(COUNT);
  const wasteCount = Math.round(COUNT * share);

  for (let i = 0; i < COUNT; i += 1) {
    phase[i] = (i / COUNT) * 0.4;
    // The wasteful share rides the bottom of the band, so the peel reads cleanly.
    waste[i] = i < wasteCount ? 1 : 0;
    laneY[i] = waste[i] === 1 ? -0.9 + Math.random() * 0.55 : -0.3 + Math.random() * 1.25;
    drift[i] = (Math.random() - 0.5) * 0.1;
  }
  return { phase, laneY, drift, waste };
}

/** smoothstep(0,1,x) — an S-curve, so the peel starts and ends gently. */
function smoothstep(x: number): number {
  const t = Math.min(1, Math.max(0, x));
  return t * t * (3 - 2 * t);
}

function Stream({ share }: { share: number }) {
  const points = useRef<THREE.Points>(null);
  const elapsed = useRef(0);
  const lanes = useMemo(() => makeLanes(share), [share]);

  // Built imperatively rather than with <bufferAttribute> JSX: fewer moving
  // parts, and the colour buffer is written once and never touched again.
  const geometry = useMemo(() => {
    const positions = new Float32Array(COUNT * 3);
    const colors = new Float32Array(COUNT * 3);
    const teal = new THREE.Color(HERO_COLORS.teal);
    const coral = new THREE.Color(HERO_COLORS.coral);

    for (let i = 0; i < COUNT; i += 1) {
      positions[i * 3] = X_START;
      positions[i * 3 + 1] = lanes.laneY[i];
      positions[i * 3 + 2] = (Math.random() - 0.5) * 0.6;
      const color = lanes.waste[i] === 1 ? coral : teal;
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return geo;
  }, [lanes]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame((_state, delta) => {
    // ONE SHOT: past DURATION the buffer is never written again — no loop.
    if (elapsed.current >= DURATION || points.current === null) return;
    elapsed.current = Math.min(DURATION, elapsed.current + delta);

    const attribute = geometry.getAttribute("position") as THREE.BufferAttribute;
    const array = attribute.array as Float32Array;
    const clock = elapsed.current / DURATION;

    for (let i = 0; i < COUNT; i += 1) {
      const phase = lanes.phase[i];
      const progress = Math.min(1, Math.max(0, (clock - phase) / (1 - phase)));
      array[i * 3] = X_START + (X_END - X_START) * progress;

      const peel = lanes.waste[i] === 1 ? smoothstep((progress - SPLIT) / (1 - SPLIT)) : 0;
      array[i * 3 + 1] = lanes.laneY[i] + lanes.drift[i] * progress - 2.2 * peel;
    }

    attribute.needsUpdate = true;
  });

  return (
    <points geometry={geometry} ref={points}>
      <PointMaterial depthWrite={false} size={0.055} sizeAttenuation transparent vertexColors />
    </points>
  );
}

/**
 * The single bold animation in the product: budget flows left to right, the
 * wasted share peels downward in coral, and after ~4s everything stops. No
 * loop, no scroll trigger. Only mounted when the visitor has NOT asked for
 * reduced motion, and only through next/dynamic(ssr:false).
 */
export default function FlowParticles({ totalSpend, headlineWaste }: Props) {
  const share = wasteShare(headlineWaste, totalSpend);

  return (
    <Canvas
      camera={{ fov: 48, position: [0, 0, 7] }}
      dpr={[1, 2]}
      gl={{ alpha: true, antialias: true }}
      style={{ height: "100%", width: "100%" }}
    >
      <Stream share={share} />
    </Canvas>
  );
}
```

- [ ] **Step 6: Write `Hero.tsx`**

`frontend/src/components/hero/Hero.tsx`:
```tsx
"use client";

import dynamic from "next/dynamic";

import FlowStatic from "@/components/hero/FlowStatic";
import { useReducedMotion } from "@/lib/motion";

// Three.js is large. Behind dynamic(ssr:false) the tables and numbers never
// wait for it, and it never runs on the server. ssr:false is legal here only
// because this file is itself a client component.
const FlowParticles = dynamic(() => import("@/components/hero/FlowParticles"), {
  ssr: false,
  loading: () => null,
});

type Props = { totalSpend: number; headlineWaste: number };

export default function Hero({ totalSpend, headlineWaste }: Props) {
  const reduced = useReducedMotion();

  if (reduced) {
    return <FlowStatic headlineWaste={headlineWaste} totalSpend={totalSpend} />;
  }
  return <FlowParticles headlineWaste={headlineWaste} totalSpend={totalSpend} />;
}
```

- [ ] **Step 7: Run the tests**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/hero src/components/dashboard`
Expected: `Tests  12 passed (12)` — 6 from `FlowStatic`, 3 from `Hero`, 3 from `CountUp`. No WebGL warning appears, because `FlowParticles` was never imported for real.

- [ ] **Step 8: Typecheck — the Three.js JSX gotcha**

Run: `cd /d/ad-optimizer-project/frontend && npx tsc --noEmit`
Expected: no output. If it reports `Property 'points' does not exist on type 'JSX.IntrinsicElements'`, the installed `@react-three/fiber` is v8 (React 18 only) and never augments React 19's JSX namespace — reinstall with `npm install @react-three/fiber@^9 @react-three/drei@^10` and re-run. Do not paper over it with `// @ts-expect-error`.

- [ ] **Step 9: Watch the animation once**

Temporarily replace `frontend/src/app/dashboard/page.tsx` with:
```tsx
import Hero from "@/components/hero/Hero";

export default function DashboardPage() {
  return (
    <div className="h-[440px]">
      <Hero headlineWaste={100000} totalSpend={400000} />
    </div>
  );
}
```
`npm run dev`, log in, open `/dashboard`.
Expected: particles sweep left to right; roughly a quarter of them are coral and visibly peel downward past the halfway point; everything comes to rest after about four seconds and **stays still** — no loop, no restart on scroll. Then open DevTools → ⋮ → More tools → **Rendering** → **Emulate CSS media feature prefers-reduced-motion: reduce** and reload: the static SVG from Task 7 appears instead, with no movement. Turn the emulation off and **restore `page.tsx` to the Task 5 placeholder**.

- [ ] **Step 10: Commit**

```bash
cd /d/ad-optimizer-project/frontend
npm test && npm run lint && npm run build
cd /d/ad-optimizer-project
git add frontend/src
git commit -m "feat(frontend): one-shot particle hero with reduced-motion fallback and synced count-up"
```

---

### Task 9: `SegmentTable` — one tab per dimension, hairline dividers

**Files:**
- Create: `frontend/src/components/tables/SegmentTable.tsx`
- Test: `frontend/src/components/tables/SegmentTable.test.tsx`

**Interfaces:**
- Consumes: `DimensionOut`, `SegmentOut`, `DIMENSION_LABELS` (Task 3); `formatPKR`, `humanizeSegment` (Task 3).
- Produces:
  ```tsx
  SegmentTable(props: { dimensions: DimensionOut[] })   // "use client" (tab state)
  ```
  Every row carries `data-flagged="true|false"` and `data-significant="true|false"` so tests and Stage 6 can key off the state rather than off class names. **No animation, no hover effect on rows** — this component is reused by the admin panel.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/tables/SegmentTable.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import SegmentTable from "./SegmentTable";
import type { DimensionOut, SegmentOut } from "@/lib/types";

function segment(overrides: Partial<SegmentOut> & { segment: string }): SegmentOut {
  return {
    spend: 0,
    impressions: 0,
    clicks: 0,
    conversions: 0,
    revenue: 0,
    cpa: null,
    ctr: null,
    cvr: null,
    roas: null,
    is_significant: true,
    is_flagged: false,
    wasted_spend: 0,
    flag_reason: null,
    ...overrides,
  };
}

const dimensions: DimensionOut[] = [
  {
    dimension: "placement",
    benchmark_cpa: 800,
    total_spend: 100000,
    total_wasted_spend: 52000,
    segments: [
      segment({
        segment: "audience_network",
        spend: 84000,
        conversions: 40,
        cpa: 2100,
        is_flagged: true,
        wasted_spend: 52000,
        flag_reason: "high_cpa",
      }),
      segment({ segment: "feed", spend: 15000, conversions: 30, cpa: 500 }),
      segment({ segment: "reels", spend: 1000, conversions: 0, is_significant: false }),
    ],
  },
  {
    dimension: "age_group",
    benchmark_cpa: 800,
    total_spend: 100000,
    total_wasted_spend: 12000,
    segments: [segment({ segment: "55-64", spend: 20000, conversions: 5, cpa: 4000, is_flagged: true, wasted_spend: 12000 })],
  },
  {
    dimension: "time_slot",
    benchmark_cpa: null,
    total_spend: 0,
    total_wasted_spend: 0,
    segments: [],
  },
];

describe("SegmentTable", () => {
  it("offers one tab per dimension with the first one selected", () => {
    render(<SegmentTable dimensions={dimensions} />);

    expect(screen.getAllByRole("tab")).toHaveLength(3);
    expect(screen.getByRole("tab", { name: "Placement" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Age group" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tab", { name: "Time slot" })).toBeInTheDocument();
  });

  it("shows the active dimension's segments with humanised names and PKR amounts", () => {
    render(<SegmentTable dimensions={dimensions} />);

    expect(screen.getByText("Audience Network")).toBeInTheDocument();
    expect(screen.getByText("Rs. 84,000")).toBeInTheDocument();
    expect(screen.getByText("Rs. 2,100")).toBeInTheDocument();
    expect(screen.getByText("Rs. 52,000")).toBeInTheDocument();
    expect(screen.queryByText("55-64")).not.toBeInTheDocument();
  });

  it("states the benchmark the flags were measured against", () => {
    render(<SegmentTable dimensions={dimensions} />);

    expect(screen.getByTestId("benchmark-line")).toHaveTextContent(
      "Benchmark CPA Rs. 800 · Rs. 52,000 wasted of Rs. 100,000",
    );
  });

  it("marks flagged rows in coral and mutes rows with too little data", () => {
    render(<SegmentTable dimensions={dimensions} />);

    const flagged = screen.getByText("Audience Network").closest("tr");
    expect(flagged).toHaveAttribute("data-flagged", "true");
    expect(flagged).toHaveClass("text-coral");

    const clean = screen.getByText("Feed").closest("tr");
    expect(clean).toHaveAttribute("data-flagged", "false");
    expect(clean).not.toHaveClass("text-coral");

    const tiny = screen.getByText("Reels").closest("tr");
    expect(tiny).toHaveAttribute("data-significant", "false");
    expect(tiny).toHaveTextContent("too little data");
  });

  it("switches dimension when a tab is clicked", async () => {
    const user = userEvent.setup();
    render(<SegmentTable dimensions={dimensions} />);

    await user.click(screen.getByRole("tab", { name: "Age group" }));

    expect(screen.getByText("55-64")).toBeInTheDocument();
    expect(screen.queryByText("Audience Network")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Age group" })).toHaveAttribute("aria-selected", "true");
  });

  it("explains an empty dimension instead of showing a bare table", async () => {
    const user = userEvent.setup();
    render(<SegmentTable dimensions={dimensions} />);

    await user.click(screen.getByRole("tab", { name: "Time slot" }));

    expect(screen.getByText(/No rows in this upload carry a time slot/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("uses hairline dividers and no zebra striping", () => {
    const { container } = render(<SegmentTable dimensions={dimensions} />);

    expect(container.querySelector("tbody")).toHaveClass("divide-y", "divide-slate/20");
    expect(container.innerHTML).not.toContain("odd:bg");
  });

  it("renders nothing when there are no dimensions at all", () => {
    const { container } = render(<SegmentTable dimensions={[]} />);

    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/tables/SegmentTable.test.tsx`
Expected: FAIL — `Failed to resolve import "./SegmentTable"`.

- [ ] **Step 3: Write `SegmentTable.tsx`**

`frontend/src/components/tables/SegmentTable.tsx`:
```tsx
"use client";

import { useState } from "react";

import { formatPKR, humanizeSegment } from "@/lib/format";
import { DIMENSION_LABELS, type DimensionOut } from "@/lib/types";

/**
 * The breakdown table. Reused unchanged by Stage 6's admin panel, so it stays
 * animation-free: no transitions on rows, no hover effect, no motion.
 */
export default function SegmentTable({ dimensions }: { dimensions: DimensionOut[] }) {
  const [active, setActive] = useState(0);
  const dimension = dimensions[active];
  if (dimension === undefined) return null;

  const label = DIMENSION_LABELS[dimension.dimension];

  return (
    <section aria-labelledby="breakdown-heading">
      <h2 className="font-display text-2xl" id="breakdown-heading">
        Where the money went
      </h2>

      <div aria-label="Breakdown dimension" className="mt-6 flex flex-wrap gap-6 border-b border-slate/20" role="tablist">
        {dimensions.map((candidate, index) => (
          <button
            aria-selected={index === active}
            className={`-mb-px border-b-2 pb-3 text-sm transition-colors ${
              index === active ? "border-teal text-paper" : "border-transparent text-slate hover:text-paper"
            }`}
            key={candidate.dimension}
            onClick={() => setActive(index)}
            role="tab"
            type="button"
          >
            {DIMENSION_LABELS[candidate.dimension]}
          </button>
        ))}
      </div>

      <p className="mt-4 text-sm text-slate" data-testid="benchmark-line">
        Benchmark CPA {dimension.benchmark_cpa === null ? "—" : formatPKR(dimension.benchmark_cpa)} ·{" "}
        {formatPKR(dimension.total_wasted_spend)} wasted of {formatPKR(dimension.total_spend)}
      </p>

      {dimension.segments.length === 0 ? (
        <p className="mt-8 max-w-xl text-slate">
          No rows in this upload carry a {label.toLowerCase()} value. Ad platforms cannot always export every
          breakdown together — upload a second export with this breakdown to see it here.
        </p>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-slate/20 text-left text-xs uppercase tracking-[0.14em] text-slate">
                <th className="py-3 pr-4 font-normal" scope="col">
                  {label}
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  Spend
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  Conversions
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  CPA
                </th>
                <th className="py-3 text-right font-normal" scope="col">
                  Wasted
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate/20">
              {dimension.segments.map((segment) => (
                <tr
                  className={
                    segment.is_flagged ? "text-coral" : segment.is_significant ? "text-paper" : "text-slate/60"
                  }
                  data-flagged={segment.is_flagged}
                  data-significant={segment.is_significant}
                  key={segment.segment}
                >
                  <td className="py-3 pr-4">
                    {humanizeSegment(segment.segment)}
                    {segment.is_significant ? null : (
                      <span className="ml-2 text-[0.65rem] uppercase tracking-[0.14em]">too little data</span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-right tabular-nums">{formatPKR(segment.spend)}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{segment.conversions}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">
                    {segment.cpa === null ? "—" : formatPKR(segment.cpa)}
                  </td>
                  <td className="py-3 text-right tabular-nums">
                    {segment.wasted_spend > 0 ? formatPKR(segment.wasted_spend) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Run the test**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/tables/SegmentTable.test.tsx`
Expected: `Tests  8 passed (8)`.

- [ ] **Step 5: Commit**

```bash
cd /d/ad-optimizer-project/frontend
npm test && npx tsc --noEmit && npm run lint
cd /d/ad-optimizer-project
git add frontend/src
git commit -m "feat(frontend): per-dimension segment table with hairline dividers and coral flags"
```

---

### Task 10: `RecommendationList` — expand on click with Framer Motion

**Files:**
- Create: `frontend/src/components/recommendations/RecommendationList.tsx`
- Test: `frontend/src/components/recommendations/RecommendationList.test.tsx`

**Interfaces:**
- Consumes: `RecommendationOut`, `DIMENSION_LABELS` (Task 3); `formatPKR`, `humanizeSegment` (Task 3); `framer-motion` (Task 2).
- Produces:
  ```tsx
  RecommendationList(props: { recommendations: RecommendationOut[] })   // "use client"
  ```
  One open item at a time. The trigger is a `<button aria-expanded>`; the reason lives in the panel it controls. This is the **only** Framer Motion in the product, and it is user-triggered.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/recommendations/RecommendationList.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import RecommendationList from "./RecommendationList";
import type { RecommendationOut } from "@/lib/types";

const recommendations: RecommendationOut[] = [
  {
    id: 1,
    dimension: "placement",
    segment_name: "audience_network",
    current_spend: 84000,
    recommended_cut: 50400,
    reason:
      "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — 2.6× your placement average of Rs. 800. Cut Rs. 50,400 (60%).",
  },
  {
    id: 2,
    dimension: "age_group",
    segment_name: "55-64",
    current_spend: 20000,
    recommended_cut: 12000,
    reason: "55-64 spent Rs. 20,000 at Rs. 4,000 per conversion — 5.0× your age group average of Rs. 800. Cut Rs. 12,000 (60%).",
  },
];

describe("RecommendationList", () => {
  it("lists every recommendation collapsed, showing the cut and the dimension", () => {
    render(<RecommendationList recommendations={recommendations} />);

    expect(screen.getByRole("button", { name: /Audience Network/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Cut Rs. 50,400")).toBeInTheDocument();
    expect(screen.getByText("Placement")).toBeInTheDocument();
    expect(screen.queryByText(recommendations[0].reason)).not.toBeInTheDocument();
  });

  it("reveals the reason when the row is clicked", async () => {
    const user = userEvent.setup();
    render(<RecommendationList recommendations={recommendations} />);

    await user.click(screen.getByRole("button", { name: /Audience Network/ }));

    expect(await screen.findByText(recommendations[0].reason)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Audience Network/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Currently spending Rs. 84,000")).toBeInTheDocument();
  });

  it("collapses again on a second click", async () => {
    const user = userEvent.setup();
    render(<RecommendationList recommendations={recommendations} />);
    const trigger = screen.getByRole("button", { name: /Audience Network/ });

    await user.click(trigger);
    await screen.findByText(recommendations[0].reason);
    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await waitFor(
      () => expect(screen.queryByText(recommendations[0].reason)).not.toBeInTheDocument(),
      { timeout: 3000 },
    );
  });

  it("keeps only one item open at a time", async () => {
    const user = userEvent.setup();
    render(<RecommendationList recommendations={recommendations} />);

    await user.click(screen.getByRole("button", { name: /Audience Network/ }));
    await user.click(screen.getByRole("button", { name: /55-64/ }));

    expect(screen.getByRole("button", { name: /55-64/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /Audience Network/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("says so plainly when nothing needs cutting", () => {
    render(<RecommendationList recommendations={[]} />);

    expect(screen.getByText(/No segment is spending above the benchmark/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/recommendations/RecommendationList.test.tsx`
Expected: FAIL — `Failed to resolve import "./RecommendationList"`.

- [ ] **Step 3: Write `RecommendationList.tsx`**

`frontend/src/components/recommendations/RecommendationList.tsx`:
```tsx
"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { formatPKR, humanizeSegment } from "@/lib/format";
import { DIMENSION_LABELS, type RecommendationOut } from "@/lib/types";

/**
 * The only Framer Motion in the product, and it only ever runs because the
 * visitor clicked. No scroll triggers, no hover animation.
 */
export default function RecommendationList({ recommendations }: { recommendations: RecommendationOut[] }) {
  const [openId, setOpenId] = useState<number | null>(null);

  if (recommendations.length === 0) {
    return (
      <p className="mt-6 max-w-xl text-slate">
        Nothing to cut this period — No segment is spending above the benchmark by enough to flag.
      </p>
    );
  }

  return (
    <ul className="mt-6 divide-y divide-slate/20 border-t border-slate/20">
      {recommendations.map((recommendation) => {
        const open = openId === recommendation.id;
        const panelId = `recommendation-${recommendation.id}`;

        return (
          <li key={recommendation.id}>
            <button
              aria-controls={panelId}
              aria-expanded={open}
              className="flex w-full flex-wrap items-baseline justify-between gap-x-6 gap-y-2 py-5 text-left"
              onClick={() => setOpenId(open ? null : recommendation.id)}
              type="button"
            >
              <span>
                <span className="font-display text-lg">{humanizeSegment(recommendation.segment_name)}</span>
                <span className="ml-3 text-xs uppercase tracking-[0.14em] text-slate">
                  {DIMENSION_LABELS[recommendation.dimension]}
                </span>
              </span>
              <span className="whitespace-nowrap font-display text-lg text-coral">
                Cut {formatPKR(recommendation.recommended_cut)}
              </span>
            </button>

            <AnimatePresence initial={false}>
              {open ? (
                <motion.div
                  animate={{ height: "auto", opacity: 1 }}
                  className="overflow-hidden"
                  exit={{ height: 0, opacity: 0 }}
                  id={panelId}
                  initial={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22, ease: "easeOut" }}
                >
                  <div className="flex flex-col gap-2 pb-6">
                    <p className="max-w-2xl text-slate">{recommendation.reason}</p>
                    <p className="text-xs uppercase tracking-[0.14em] text-slate">
                      Currently spending {formatPKR(recommendation.current_spend)}
                    </p>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </li>
        );
      })}
    </ul>
  );
}
```

- [ ] **Step 4: Run the test**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/recommendations/RecommendationList.test.tsx`
Expected: `Tests  5 passed (5)`. If the collapse test flakes because Framer Motion's exit animation has not finished inside jsdom, raise that one `waitFor` timeout — do **not** delete the assertion and do **not** drop `AnimatePresence`.

- [ ] **Step 5: Commit**

```bash
cd /d/ad-optimizer-project/frontend
npm test && npx tsc --noEmit && npm run lint
cd /d/ad-optimizer-project
git add frontend/src
git commit -m "feat(frontend): recommendation list that expands to the reasoning on click"
```

---

### Task 11: `ReportView` — the asymmetric layout, plus both report routes

**Files:**
- Create: `frontend/src/components/ui/Stat.tsx`
- Create: `frontend/src/components/ui/EmptyState.tsx`
- Create: `frontend/src/components/dashboard/SummaryNumbers.tsx`
- Create: `frontend/src/components/dashboard/ReportView.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx` (replace the Task 5 placeholder)
- Create: `frontend/src/app/dashboard/reports/[runId]/page.tsx`
- Test: `frontend/src/components/dashboard/ReportView.test.tsx`

**Interfaces:**
- Consumes: `Hero` (Task 8), `CountUp` (Task 8), `SegmentTable` (Task 9), `RecommendationList` (Task 10), `getLatestReport`/`getReport`/`getUploads` (Task 5), `formatPKR`/`formatPct` (Task 3).
- Produces:
  ```tsx
  Stat(props: { label: string; accent?: boolean; children: React.ReactNode })
  EmptyState(props: { title: string; body: string; action?: React.ReactNode })
  SummaryNumbers(props: { totalSpend: number; headlineWaste: number; recoveryPct: number; animate: boolean })  // "use client"
  ReportView(props: { report: ReportOut; hero?: boolean })   // hero defaults to true; Stage 6 passes hero={false}
  ```
  Routes `/dashboard` and `/dashboard/reports/[runId]`.

**Layout contract (spec §6 Stage 4):** on `lg` and wider, one grid row of `[3fr_2fr]` and `lg:min-h-[60vh]` — the hero is the 3fr column (≈60% of the first screen), the numbers the 2fr column. Below `lg` it becomes one column with the numbers first, so a phone sees the figure before the picture. Numbers are bare `font-display` type: no card, no border, no panel.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/dashboard/ReportView.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportView from "./ReportView";
import type { ReportOut } from "@/lib/types";

// The hero is covered by Hero.test.tsx / FlowStatic.test.tsx; here we only care
// that ReportView mounts it (or does not).
vi.mock("@/components/hero/Hero", () => ({
  default: () => <div data-testid="hero" />,
}));

const report: ReportOut = {
  run_id: 5,
  upload_id: 12,
  generated_at: "2026-09-16T09:10:00Z",
  date_range_start: "2026-08-01",
  date_range_end: "2026-08-31",
  total_spend: 400000,
  headline_waste: 100000,
  recovery_pct: 25,
  dimensions: [
    {
      dimension: "placement",
      benchmark_cpa: 800,
      total_spend: 400000,
      total_wasted_spend: 100000,
      segments: [
        {
          segment: "audience_network",
          spend: 84000,
          impressions: 90000,
          clicks: 900,
          conversions: 40,
          revenue: 0,
          cpa: 2100,
          ctr: 0.01,
          cvr: 0.04,
          roas: null,
          is_significant: true,
          is_flagged: true,
          wasted_spend: 52000,
          flag_reason: "high_cpa",
        },
      ],
    },
  ],
  recommendations: [
    {
      id: 1,
      dimension: "placement",
      segment_name: "audience_network",
      current_spend: 84000,
      recommended_cut: 50400,
      reason: "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion.",
    },
  ],
  config_snapshot: { benchmark_mode: "account_avg", waste_multiplier: 1.5 },
};

describe("ReportView", () => {
  it("shows the three headline numbers as large type", () => {
    render(<ReportView report={report} />);

    expect(screen.getByText("Total spend analysed")).toBeInTheDocument();
    expect(screen.getByText("Estimated waste")).toBeInTheDocument();
    expect(screen.getByText("Recoverable share of spend")).toBeInTheDocument();
    expect(screen.getByTestId("stat-total-spend")).toHaveTextContent("Rs. 400,000");
    expect(screen.getByTestId("stat-recovery-pct")).toHaveTextContent("25.0%");
    expect(screen.getByTestId("stat-total-spend")).toHaveClass("font-display");
  });

  it("puts the hero beside the numbers in a 3fr/2fr row about 60vh tall", () => {
    render(<ReportView report={report} />);

    expect(screen.getByTestId("hero")).toBeInTheDocument();
    const band = screen.getByTestId("hero-band");
    expect(band.className).toContain("lg:grid-cols-[3fr_2fr]");
    expect(band.className).toContain("lg:min-h-[60vh]");
    expect(band.className).toContain("grid-cols-1");
  });

  it("renders the tables and the recommendations", () => {
    render(<ReportView report={report} />);

    expect(screen.getByRole("tab", { name: "Placement" })).toBeInTheDocument();
    expect(screen.getAllByText("Audience Network").length).toBeGreaterThan(0);
    expect(screen.getByText("Cut Rs. 50,400")).toBeInTheDocument();
  });

  it("links to the PDF for this run and states the date range", () => {
    render(<ReportView report={report} />);

    expect(screen.getByRole("link", { name: "Download PDF" })).toHaveAttribute("href", "/api/reports/5/pdf");
    expect(screen.getByText(/2026-08-01/)).toHaveTextContent("Run #5 · 2026-08-01 to 2026-08-31");
  });

  it("names the benchmark the numbers were measured against", () => {
    render(<ReportView report={report} />);

    expect(screen.getByText(/account_avg/)).toBeInTheDocument();
  });

  it("drops the hero entirely for admin views", () => {
    render(<ReportView hero={false} report={report} />);

    expect(screen.queryByTestId("hero")).not.toBeInTheDocument();
    expect(screen.getByTestId("stat-total-spend")).toHaveTextContent("Rs. 400,000");
    expect(screen.getByRole("tab", { name: "Placement" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to watch it fail**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/dashboard/ReportView.test.tsx`
Expected: FAIL — `Failed to resolve import "./ReportView"`.

- [ ] **Step 3: Write `Stat.tsx` and `EmptyState.tsx`**

`frontend/src/components/ui/Stat.tsx`:
```tsx
import type { ReactNode } from "react";

/**
 * A key number as large type — deliberately NOT a card: no border, no
 * background, no shadow (docs/PLAN.md §6 Stage 4).
 */
export default function Stat({
  label,
  accent = false,
  testId,
  children,
}: {
  label: string;
  accent?: boolean;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-slate">{label}</p>
      <p
        className={`mt-2 font-display text-4xl leading-none tabular-nums sm:text-5xl lg:text-6xl ${
          accent ? "text-coral" : "text-paper"
        }`}
        data-testid={testId}
      >
        {children}
      </p>
    </div>
  );
}
```

`frontend/src/components/ui/EmptyState.tsx`:
```tsx
import type { ReactNode } from "react";

export default function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="max-w-xl py-16">
      <h1 className="font-display text-4xl leading-tight">{title}</h1>
      <p className="mt-4 text-slate">{body}</p>
      {action ? <div className="mt-8">{action}</div> : null}
    </div>
  );
}
```

- [ ] **Step 4: Write `SummaryNumbers.tsx`**

`frontend/src/components/dashboard/SummaryNumbers.tsx`:
```tsx
"use client";

import CountUp from "@/components/dashboard/CountUp";
import Stat from "@/components/ui/Stat";
import { formatPKR, formatPct } from "@/lib/format";
import { useReducedMotion } from "@/lib/motion";

type Props = {
  totalSpend: number;
  headlineWaste: number;
  recoveryPct: number;
  animate: boolean;
};

/**
 * The right-hand column. Only the waste figure counts up, and only when the
 * hero is animating too — so the number and the coral drip land together.
 */
export default function SummaryNumbers({ totalSpend, headlineWaste, recoveryPct, animate }: Props) {
  const reduced = useReducedMotion();
  const counting = animate && !reduced;

  return (
    <div className="flex flex-col justify-center gap-10">
      <Stat label="Total spend analysed" testId="stat-total-spend">
        {formatPKR(totalSpend)}
      </Stat>
      <Stat accent label="Estimated waste" testId="stat-headline-waste">
        <CountUp animate={counting} value={headlineWaste} />
      </Stat>
      <Stat label="Recoverable share of spend" testId="stat-recovery-pct">
        {formatPct(recoveryPct)}
      </Stat>
    </div>
  );
}
```

- [ ] **Step 5: Write `ReportView.tsx`**

`frontend/src/components/dashboard/ReportView.tsx`:
```tsx
import SummaryNumbers from "@/components/dashboard/SummaryNumbers";
import Hero from "@/components/hero/Hero";
import RecommendationList from "@/components/recommendations/RecommendationList";
import SegmentTable from "@/components/tables/SegmentTable";
import type { ReportOut } from "@/lib/types";

type Props = { report: ReportOut; hero?: boolean };

/**
 * The whole client-facing report. Stage 6's admin views render this with
 * hero={false}: same numbers, same tables, no animation at all.
 */
export default function ReportView({ report, hero = true }: Props) {
  const benchmarkMode = String(report.config_snapshot.benchmark_mode ?? "account_avg");

  return (
    <div>
      <section
        className="grid grid-cols-1 items-center gap-10 lg:min-h-[60vh] lg:grid-cols-[3fr_2fr] lg:gap-16"
        data-testid="hero-band"
      >
        {hero ? (
          <div className="order-2 min-h-[260px] sm:min-h-[340px] lg:order-1 lg:min-h-[440px]">
            <Hero headlineWaste={report.headline_waste} totalSpend={report.total_spend} />
          </div>
        ) : null}
        <div className={hero ? "order-1 lg:order-2" : "lg:col-span-2"}>
          <SummaryNumbers
            animate={hero}
            headlineWaste={report.headline_waste}
            recoveryPct={report.recovery_pct}
            totalSpend={report.total_spend}
          />
        </div>
      </section>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-slate/20 pt-6 text-sm text-slate">
        <p>
          Run #{report.run_id} · {report.date_range_start ?? "start unknown"} to{" "}
          {report.date_range_end ?? "end unknown"}
        </p>
        <a
          className="text-teal underline underline-offset-4"
          href={`/api/reports/${report.run_id}/pdf`}
        >
          Download PDF
        </a>
      </div>

      <div className="mt-16">
        <SegmentTable dimensions={report.dimensions} />
      </div>

      <section aria-labelledby="recommendations-heading" className="mt-20">
        <h2 className="font-display text-2xl" id="recommendations-heading">
          What to cut first
        </h2>
        <RecommendationList recommendations={report.recommendations} />
      </section>

      <p className="mt-16 max-w-2xl text-xs text-slate">
        Waste is the spend above what these conversions should have cost, measured against the {benchmarkMode}{" "}
        benchmark. Figures are never added up across breakdowns — the headline is the largest single
        breakdown, so nothing is counted twice.
      </p>
    </div>
  );
}
```

The PDF link points at the Stage 5 endpoint (`GET /api/reports/{run_id}/pdf`). Until Stage 5 ships it answers 404 — render the link anyway, as planned.

- [ ] **Step 6: Run the test**

Run: `cd /d/ad-optimizer-project/frontend && npx vitest run src/components/dashboard/ReportView.test.tsx`
Expected: `Tests  6 passed (6)`.

- [ ] **Step 7: Write the two routes**

`frontend/src/app/dashboard/page.tsx` — replaces the Task 5 placeholder:
```tsx
import Link from "next/link";

import ReportView from "@/components/dashboard/ReportView";
import EmptyState from "@/components/ui/EmptyState";
import { getLatestReport, getUploads } from "@/lib/server-api";

export const metadata = { title: "Report · Ad Spend Optimization" };

export default async function DashboardPage() {
  const report = await getLatestReport();
  if (report !== null) {
    return <ReportView report={report} />;
  }

  // No approved report. Two different empty states, and they are not the same
  // story: "you have not uploaded anything" vs "we are still checking it".
  const uploads = await getUploads();
  if (uploads.length > 0) {
    return (
      <EmptyState
        action={
          <Link className="text-teal underline underline-offset-4" href="/dashboard/upload">
            Upload another export
          </Link>
        }
        body="We review every analysis by hand before it reaches you, so the numbers on your invoice are numbers we stand behind. Your report appears here as soon as it is approved."
        title="Your analysis is with our reviewer."
      />
    );
  }

  return (
    <EmptyState
      action={
        <Link className="text-teal underline underline-offset-4" href="/dashboard/upload">
          Upload your first CSV
        </Link>
      }
      body="Export your ad data with the placement, age and time-of-day breakdowns, upload it, and we will show you which segments are burning money."
      title="Nothing to show yet."
    />
  );
}
```

`frontend/src/app/dashboard/reports/[runId]/page.tsx`:
```tsx
import { notFound } from "next/navigation";

import ReportView from "@/components/dashboard/ReportView";
import { getReport } from "@/lib/server-api";

export const metadata = { title: "Report · Ad Spend Optimization" };

// Next 16: route params arrive as a Promise.
export default async function RunReportPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const report = await getReport(runId);

  // The backend answers 404 for another tenant's run AND for an unapproved one,
  // so this single branch covers both (docs/PLAN.md §4 "Tenant isolation").
  if (report === null) {
    notFound();
  }

  return <ReportView report={report} />;
}
```

- [ ] **Step 8: Full check and commit**

```bash
cd /d/ad-optimizer-project/frontend
npm test && npx tsc --noEmit && npm run lint && npm run build
```
Expected: all tests pass; the build's route table lists `/dashboard`, `/dashboard/upload` and `/dashboard/reports/[runId]`, each marked as dynamically rendered (they read cookies).
```bash
cd /d/ad-optimizer-project
git add frontend/src
git commit -m "feat(frontend): asymmetric report view, dashboard summary and per-run report route"
```

---

### Task 12: Landing page, CI, green gate, owner checklist

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Create or Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: no new code interfaces. CI runs `npm test` alongside lint, typecheck and build.

- [ ] **Step 1: Point the landing page at the product**

`frontend/src/app/page.tsx`:
```tsx
import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6 py-24">
      <p className="text-sm uppercase tracking-widest text-slate">Ad Spend Optimization</p>
      <h1 className="font-display text-5xl leading-tight sm:text-6xl">
        Find the money leaking out of your ads.
      </h1>
      <p className="max-w-xl text-slate">
        Upload one export. We compare every placement, age group and time slot against your own account
        average and show you, in rupees, what to cut.
      </p>
      <div className="mt-4 flex flex-wrap gap-6 text-sm">
        <Link className="text-teal underline underline-offset-4" href="/signup">
          Create an account
        </Link>
        <Link className="text-slate underline underline-offset-4 transition-colors hover:text-paper" href="/login">
          Log in
        </Link>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Make CI run the frontend tests**

If `.github/workflows/ci.yml` exists (Stage 0 Task 8), add one line to the `frontend` job so it reads:
```yaml
      - run: npm ci
      - run: npm run lint
      - run: npx tsc --noEmit
      - run: npm test
      - run: npm run build
```

If the file does **not** exist — Stage 0 Task 8 was never run — create `.github/workflows/ci.yml` with exactly this:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    env:
      ENV: test
      DATABASE_URL: sqlite+pysqlite:///:memory:
      SECRET_KEY: ci-secret
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements-dev.txt
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest
      - name: Migration applies from empty
        run: DATABASE_URL=sqlite:///./ci.db alembic upgrade head

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "24"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npx tsc --noEmit
      - run: npm test
      - run: npm run build
```

- [ ] **Step 3: Document the frontend in the README**

Append to `README.md`:
````markdown
### Client dashboard (Stage 4)

```bash
cd backend && .venv/Scripts/uvicorn app.main:app --port 8000   # terminal 1
cd frontend && npm run dev                                     # terminal 2
```

Open http://localhost:3000. `/dashboard/*` is behind a server-side auth guard that
forwards your cookies to `GET /api/auth/me`.

```bash
cd frontend
npm test            # Vitest + React Testing Library
npm run test:watch
```

The hero animation plays once on load and stops. Set
**DevTools → Rendering → Emulate prefers-reduced-motion: reduce** to see the
static SVG fallback instead.
````

- [ ] **Step 4: Run the whole gate**

```bash
cd /d/ad-optimizer-project/frontend
npm run lint && npx tsc --noEmit && npm test && npm run build
```
Expected, in order:
- eslint: no output.
- `tsc`: no output.
- Vitest: `Test Files  12 passed (12)` — `format`, `api`, `server-api`, `AuthForm`, `LogoutButton`, `UploadPanel`, `FlowStatic`, `Hero`, `CountUp`, `SegmentTable`, `RecommendationList`, `ReportView`. What matters is **0 failed**.
- `next build`: ends with a route table containing `/`, `/login`, `/signup`, `/dashboard`, `/dashboard/upload`, `/dashboard/reports/[runId]`.

If any command fails, fix it here — do not commit a red gate.

- [ ] **Step 5: Commit**

```bash
cd /d/ad-optimizer-project
git add frontend/src/app/page.tsx .github/workflows/ci.yml README.md
git commit -m "chore(frontend): landing page links, CI runs vitest, README instructions"
```

- [ ] **Step 6: Owner's manual checklist (the Stage 4 checkpoint)**

Start both servers, sign up a fresh client, and walk it through. Tick each line.

- [ ] `/` → "Create an account" → sign up → lands on `/dashboard` showing **"Nothing to show yet."**
- [ ] `/dashboard/upload` → drag `backend/tests/fixtures/sample_30d.csv` onto the drop zone → filename, row count and date range appear.
- [ ] Upload a deliberately broken CSV (edit one `spend` cell to `abc`) → a table of **row-level** errors with the row number and column, and **no** Analyze button.
- [ ] Re-upload the good file → **Analyze** → the status text moves Queued → Running → **"awaiting admin review"** within a few seconds. Watch the Network tab: `/api/runs/{id}` is polled every ~2s and **stops** once the run is done.
- [ ] Approve the run in the database (`UPDATE analysis_runs SET review_status='approved' WHERE id=…`; Stage 6 gives this a UI) → reload `/dashboard` → the report renders.
- [ ] Hero: particles sweep left→right, the coral share peels downward, the waste number counts up alongside it, and **everything stops after ~4 seconds**. Scroll down and back up — nothing re-animates.
- [ ] DevTools → ⋮ → More tools → **Rendering** → **Emulate CSS media feature prefers-reduced-motion: reduce** → reload → the **static SVG** hero, no count-up, same numbers.
- [ ] Breakdown tables: three tabs; flagged rows are coral; not-significant rows are muted and marked "too little data"; the benchmark line above the table matches the report.
- [ ] Recommendations: clicking a row expands it to the plain-language reason; clicking again collapses it; only one is open at a time.
- [ ] **Download PDF** link is present (it 404s until Stage 5 — expected).
- [ ] DevTools device toolbar at **400 × 800**: the numbers sit above the hero, nothing is clipped, and the page does **not** scroll sideways. Only the two tables scroll horizontally, inside their own boxes.
- [ ] Log out → `/dashboard` redirects to `/login`. Paste another client's run id into `/dashboard/reports/{id}` → Next's 404 page (the backend answers 404 for a foreign tenant).

---

## Stage 4 exit checklist (from `docs/PLAN.md` §6)

- [ ] The dashboard renders real data end to end (Task 12 Step 6).
- [ ] Reduced motion shows the static version (Task 8 Step 9, Task 12 Step 6).
- [ ] It works at mobile width (Task 12 Step 6, 400px).
- [ ] Empty states exist for "no uploads yet" and "awaiting admin review" (Task 11 Step 7, Task 6 Step 4).
- [ ] `npm run lint && npx tsc --noEmit && npm test && npm run build` are all green (Task 12 Step 4).

## Decisions

1. **The 422 upload body is assumed to be `{"detail": {"errors": [...], "warnings": [...]}}`.** `extractIssues` normalises any other shape into a one-row table, so Stage 3 cannot break this page. Recorded as an addition in the header.
2. **`/api/reports/latest` "nothing yet" is handled three ways** — 404, 204, or a `200` with a `null` body all become `null`. Stage 3's plan can pick any of them.
3. **The "awaiting admin review" dashboard state is derived from `GET /api/uploads`,** not from a runs-list endpoint, because §5 defines no `GET /api/runs` list. If Stage 3 adds one, this can be sharpened later.
4. **Server components fetch straight from `BACKEND_URL`; client components go through the `/api/*` rewrite.** The rewrite exists to keep browser cookies first-party (§1 #8); a server-side hop through it would be a pointless extra round trip.
5. **`useReducedMotion()` starts at `true`.** The server render and first paint are always the static SVG, so someone who asked for no motion never catches a frame of it.
6. **Waste particles are coral from the start** rather than changing colour mid-flight. It keeps the colour buffer static (only positions are written per frame) and the peel still reads clearly.
7. **One `ReportView` with a `hero` prop** instead of a separate admin component — it is how the Global Constraint "admin views share components but never the hero" is actually enforced, and `hero={false}` also switches the count-up off.
8. **The PDF link renders now even though Stage 5 has not built the endpoint.** It was explicitly requested; it 404s until then.
9. **`vitest` runs with `globals: false`.** Every test imports its helpers from `"vitest"`, so `tsconfig.json` needs no `types` array and Next's own type setup is untouched.
10. **Rows expose `data-flagged` / `data-significant`.** Tests assert state, not Tailwind class names, so a restyle does not break the suite — and Stage 6 gets the same hooks.
11. **The nav has no Billing link yet.** Stage 7 builds `/dashboard/billing`; linking to a 404 now would be worse than not linking.
12. **Hex literals live in exactly one place outside `globals.css`: `HERO_COLORS` in `src/lib/motion.ts`.** SVG gradient stops and Three.js colour buffers cannot read Tailwind utilities; everything else uses the tokens.

## Self-review notes

- **Spec coverage against `docs/PLAN.md` §6 Stage 4:** app shell ✔ (Task 5); login/signup ✔ (Task 4); upload page with drag-drop, per-row validation errors and run status ✔ (Task 6); asymmetric summary with the hero at ~60% and big Space Grotesk numbers beside it ✔ (Task 11, `lg:grid-cols-[3fr_2fr]` + `lg:min-h-[60vh]`); breakdown tables with hairline dividers, one tab per dimension, flagged rows in coral ✔ (Task 9); Framer Motion recommendations ✔ (Task 10); hero step A static SVG driven by the real spend/waste ratio, doubling as the reduced-motion fallback ✔ (Task 7); hero step B R3F instanced points with the teal/coral split matching the waste share, a synced count-up, one shot on load, `dynamic(ssr:false)` ✔ (Task 8); empty states for no uploads and awaiting review ✔ (Task 11); mobile width ✔ (Task 12). §5 endpoints consumed: `/api/auth/{signup,login,logout,me}`, `/api/uploads`, `/api/uploads/template.csv`, `/api/analyze/{upload_id}`, `/api/runs/{id}`, `/api/reports/latest`, `/api/reports/{run_id}`, `/api/reports/{run_id}/pdf` ✔.
- **INTERFACES conformance:** `apiFetch`, `formatPKR`, `formatPct`, `src/lib/types.ts`, routes `/login`, `/signup`, `/dashboard`, `/dashboard/upload`, `/dashboard/reports/[runId]`, and components `hero/FlowStatic.tsx`, `hero/FlowParticles.tsx`, `hero/Hero.tsx`, `tables/SegmentTable.tsx`, `recommendations/RecommendationList.tsx`, `ui/*` all use the contracted names and paths verbatim. `/dashboard/billing` is listed there but belongs to Stage 7 and is deliberately not built here. Additions are listed in the header.
- **Type consistency:** `ReportOut.recovery_pct` is a 0–100 percentage everywhere (`formatPct` documents it, `ReportView` passes it straight through). `SegmentOut.cpa` / `DimensionOut.benchmark_cpa` are nullable and every render site handles `null` with an em dash. `RunOut.headline_waste` is nullable and is never formatted — only `ReportOut.headline_waste` reaches `formatPKR`. `Stat` takes `children`, not a `value` prop, in both call sites. `BAND = 140` is defined once in `FlowStatic.tsx` and the identical share arithmetic (`wasteShare`) feeds `FlowParticles`. `HERO_DURATION_MS` is the single source for both the 4s particle run and the count-up.
- **Deliberate non-goals:** no `/dashboard/billing` (Stage 7), no admin routes (Stage 6), no PDF generation (Stage 5), no Playwright/E2E (the owner's manual checklist is the Stage 4 checkpoint), no Storybook.
