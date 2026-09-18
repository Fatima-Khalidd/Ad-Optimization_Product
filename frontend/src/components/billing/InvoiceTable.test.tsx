import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import InvoiceTable from "@/components/billing/InvoiceTable";
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
    is_overdue: true,
    payments: [],
    instructions: [],
    ...overrides,
  };
}

describe("InvoiceTable", () => {
  it("marks an overdue invoice with text, not colour alone, and formats money exactly", () => {
    render(
      <InvoiceTable
        invoices={[invoice({ due_date: "2020-01-01", status: "issued" })]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getAllByText("Rs. 19,600.00")).toHaveLength(2);
  });

  it("does not mark a paid invoice as overdue even with a past due date", () => {
    render(
      <InvoiceTable
        invoices={[invoice({ due_date: "2020-01-01", status: "paid", amount_due: "0.00" })]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.queryByText("Overdue")).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no invoices", () => {
    render(<InvoiceTable invoices={[]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText(/no invoices yet/i)).toBeInTheDocument();
  });
});
