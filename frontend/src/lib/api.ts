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
 * CLIENT-ONLY. Relative paths need `document.location` to resolve against, so calling this
 * from a React Server Component throws `Failed to parse URL`. Server components must fetch
 * `${process.env.BACKEND_URL}${path}` directly and forward the request cookies by hand.
 *
 * Browser-side API client. Paths are relative ("/api/..."), so the Next.js
 * rewrite keeps the auth cookies first-party (docs/PLAN.md §1 #8).
 * Never pass a client_id — the backend reads the tenant from the cookie.
 *
 * Empty-body decision: a 204, or any other 2xx with an empty text body,
 * resolves to `undefined` (never throws on `JSON.parse("")`).
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
      // Non-JSON body (e.g. an HTML 500 page from a proxy) — discard it rather than
      // surfacing raw markup as an error message; ApiError falls back to a generic message.
      body = null;
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
 * the UI can table up. Stage 3 sends {"detail": {"status": "failed", "upload_id": N,
 * "errors": [...], "warnings": [...]}}; a plain string detail (e.g. 401's
 * "invalid credentials") wraps as a single file-level error; anything else degrades safely.
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
