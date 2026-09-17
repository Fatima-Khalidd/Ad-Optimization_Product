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
