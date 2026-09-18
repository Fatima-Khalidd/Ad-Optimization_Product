import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import InvoiceDetail from "@/components/billing/InvoiceDetail";
import type { Invoice } from "@/lib/types";

function invoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: 1,
    invoice_number: "INV-2026-0001",
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    due_date: "2026-08-14",
    base_fee: "15000.00",
    confirmed_recovered_waste: "23000.00",
    performance_fee: "4600.00",
    total: "19600.00",
    amount_paid: "0.00",
    amount_due: "19600.00",
    status: "issued",
    issued_at: "2026-08-01T00:00:00Z",
    created_at: "2026-08-01T00:00:00Z",
    is_overdue: false,
    payments: [],
    instructions: [],
    ...overrides,
  };
}

describe("InvoiceDetail", () => {
  it("clamps a negative amount owed at zero and shows an explicit overpaid line", () => {
    render(
      <InvoiceDetail
        invoice={invoice({
          status: "paid",
          total: "19600.00",
          amount_paid: "24600.00",
          amount_due: "-5000.00",
        })}
        methods={[]}
        onSubmitted={vi.fn()}
      />,
    );

    expect(screen.queryByText("Rs. -5,000.00")).not.toBeInTheDocument();
    expect(screen.getByText(/still owed/i).nextSibling).toHaveTextContent("Rs. 0.00");
    expect(screen.getByText(/overpaid by/i)).toBeInTheDocument();
    expect(screen.getAllByText("Rs. 5,000.00").length).toBeGreaterThan(0);
  });

  it("shows no overpaid line for a normal partially-paid invoice", () => {
    render(
      <InvoiceDetail
        invoice={invoice({
          status: "issued",
          total: "19600.00",
          amount_paid: "10000.00",
          amount_due: "9600.00",
        })}
        methods={[]}
        onSubmitted={vi.fn()}
      />,
    );

    expect(screen.queryByText(/overpaid by/i)).not.toBeInTheDocument();
    expect(screen.getByText(/still owed/i).nextSibling).toHaveTextContent("Rs. 9,600.00");
  });
});
