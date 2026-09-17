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

  // Controller addition: GET /api/reports/latest's 404 empty-state body must
  // round-trip through ApiError just like any other error — no special case.
  it("throws ApiError with status 404 and no body", async () => {
    stubFetch(new Response(null, { status: 404 }));

    const error = (await apiFetch("/api/reports/latest").catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
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

  // Controller addition: the 422 upload-rejection body nests errors/warnings
  // one level deeper — {"detail": {"status": "failed", "upload_id": N, "errors": [...], "warnings": [...]}}
  // — extractIssues must still find them since detail itself carries the keys.
  it("extracts errors/warnings from the upload-rejection 422 shape", () => {
    const detail = {
      status: "failed",
      upload_id: 12,
      errors: [{ row: 2, column: "campaign_id", message: "missing" }],
      warnings: [],
    };

    expect(extractIssues(detail)).toEqual({
      errors: [{ row: 2, column: "campaign_id", message: "missing" }],
      warnings: [],
    });
  });
});
