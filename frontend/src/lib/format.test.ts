import { describe, expect, it } from "vitest";

import { formatPKR, formatPKRExact, formatPct, humanizeSegment, wasteShare } from "./format";

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

  // Controller addition: the backend serialises money as a decimal STRING
  // ("-?\d+\.\d{2}"), so formatPKR must also accept that shape directly.
  it("parses backend money strings", () => {
    expect(formatPKR("84000.00")).toBe("Rs. 84,000");
    expect(formatPKR("1234.50")).toBe("Rs. 1,235");
    expect(formatPKR("-2500.00")).toBe("-Rs. 2,500");
    expect(formatPKR("0.00")).toBe("Rs. 0");
  });

  // Controller addition: null/undefined/unparseable render a dash, not "Rs. 0"
  // — that distinguishes "no value yet" from "value is zero".
  it("renders a dash for null, undefined and unparseable input", () => {
    expect(formatPKR(null)).toBe("—");
    expect(formatPKR(undefined)).toBe("—");
    expect(formatPKR("not-a-number")).toBe("—");
    expect(formatPKR("")).toBe("—");
  });
});

describe("formatPKRExact", () => {
  it("renders exactly two decimals with thousands separators, from a number", () => {
    expect(formatPKRExact(4600.5)).toBe("Rs. 4,600.50");
    expect(formatPKRExact(84000)).toBe("Rs. 84,000.00");
    expect(formatPKRExact(800.2)).toBe("Rs. 800.20");
  });

  it("renders exactly two decimals with thousands separators, from a backend string", () => {
    expect(formatPKRExact("4600.50")).toBe("Rs. 4,600.50");
    expect(formatPKRExact("19600.00")).toBe("Rs. 19,600.00");
  });

  it("handles a value already at .00", () => {
    expect(formatPKRExact("0.00")).toBe("Rs. 0.00");
    expect(formatPKRExact(0)).toBe("Rs. 0.00");
  });

  it("handles a large value without rounding away the cents", () => {
    expect(formatPKRExact("1234567.89")).toBe("Rs. 1,234,567.89");
  });

  it("handles negative amounts", () => {
    expect(formatPKRExact(-2500.5)).toBe("-Rs. 2,500.50");
  });

  it("renders a dash for null, undefined and unparseable input", () => {
    expect(formatPKRExact(null)).toBe("—");
    expect(formatPKRExact(undefined)).toBe("—");
    expect(formatPKRExact("not-a-number")).toBe("—");
    expect(formatPKRExact("")).toBe("—");
  });

  it("never renders NaN", () => {
    expect(formatPKRExact(Number.NaN)).toBe("Rs. 0.00");
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

  // Controller addition: recovery_pct arrives as a string (e.g. "16.28").
  it("parses backend percentage strings", () => {
    expect(formatPct("16.28")).toBe("16.3%");
    expect(formatPct("0.00")).toBe("0.0%");
  });

  // Controller addition: null renders a dash, matching formatPKR's rule.
  it("renders a dash for null and undefined", () => {
    expect(formatPct(null)).toBe("—");
    expect(formatPct(undefined)).toBe("—");
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
