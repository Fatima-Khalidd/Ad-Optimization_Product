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
