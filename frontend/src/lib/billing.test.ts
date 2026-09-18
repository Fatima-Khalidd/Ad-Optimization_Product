import { describe, expect, it } from "vitest";

import { isOverdue, METHOD_LABELS, STATUS_LABELS, toISODate } from "@/lib/billing";

const unpaid = { due_date: "2026-10-07", status: "issued" } as const;

describe("isOverdue", () => {
  it("is false before the due date", () => {
    expect(isOverdue(unpaid, new Date(2026, 9, 6))).toBe(false);
  });

  it("is false on the due date itself — the client still has that day", () => {
    expect(isOverdue(unpaid, new Date(2026, 9, 7))).toBe(false);
  });

  it("is true the day after the due date", () => {
    expect(isOverdue(unpaid, new Date(2026, 9, 8))).toBe(true);
  });

  it("is true while a submitted payment is still awaiting confirmation", () => {
    expect(isOverdue({ due_date: "2026-10-07", status: "payment_submitted" }, new Date(2026, 9, 8))).toBe(true);
  });

  it("is false once the invoice is paid or void, however old it is", () => {
    expect(isOverdue({ due_date: "2020-01-01", status: "paid" }, new Date(2026, 9, 8))).toBe(false);
    expect(isOverdue({ due_date: "2020-01-01", status: "void" }, new Date(2026, 9, 8))).toBe(false);
  });

  it("uses the viewer's local calendar date, not UTC", () => {
    // 23:30 local on the due date is still the due date, whatever the timezone offset.
    expect(isOverdue(unpaid, new Date(2026, 9, 7, 23, 30))).toBe(false);
    expect(toISODate(new Date(2026, 9, 7, 23, 30))).toBe("2026-10-07");
  });
});

describe("labels", () => {
  it("names every method and status a client can see", () => {
    expect(METHOD_LABELS.jazzcash).toBe("JazzCash");
    expect(METHOD_LABELS.bank_iban).toBe("Bank transfer (IBAN)");
    expect(STATUS_LABELS.payment_submitted).toBe("Awaiting confirmation");
    expect(STATUS_LABELS.issued).toBe("Unpaid");
  });
});
