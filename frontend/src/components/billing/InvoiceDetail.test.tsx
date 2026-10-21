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
    currency: "USD",
    pkr_per_usd: "1.0000",
    status: "issued",
    issued_at: "2026-08-01T00:00:00Z",
    created_at: "2026-08-01T00:00:00Z",
    is_overdue: false,
    payments: [],
    instructions: [],
    pay_by_card: false,
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

    expect(screen.queryByText("-$5,000.00")).not.toBeInTheDocument();
    expect(screen.getByText(/still owed/i).nextSibling).toHaveTextContent("$0.00");
    expect(screen.getByText(/overpaid by/i)).toBeInTheDocument();
    expect(screen.getAllByText("$5,000.00").length).toBeGreaterThan(0);
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
    expect(screen.getByText(/still owed/i).nextSibling).toHaveTextContent("$9,600.00");
  });

  it("bills in dollars but shows recovered waste in rupees, with the conversion rate", () => {
    render(
      <InvoiceDetail
        invoice={invoice({
          base_fee: "65.00",
          performance_fee: "16.67",
          total: "81.67",
          amount_due: "81.67",
          pkr_per_usd: "276.0000",
        })}
        methods={[]}
        onSubmitted={vi.fn()}
      />,
    );

    expect(screen.getByText(/performance fee on/i)).toHaveTextContent(
      "Performance fee on Rs. 23,000.00 recovered (at Rs. 276.00 per USD)",
    );
    expect(screen.getByText(/performance fee on/i).nextSibling).toHaveTextContent("$16.67");
    expect(screen.getByText(/^total$/i).nextSibling).toHaveTextContent("$81.67");
  });

  it("offers card payment first, with bank transfer as the alternative, when it is set up", () => {
    render(<InvoiceDetail invoice={invoice({ pay_by_card: true })} methods={[]} onSubmitted={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Pay $19,600.00 by card" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Or pay by bank transfer" })).toBeInTheDocument();
  });

  it("offers no card button when card payments are not set up or nothing is owed", () => {
    const { rerender } = render(<InvoiceDetail invoice={invoice()} methods={[]} onSubmitted={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /by card/i })).not.toBeInTheDocument();

    rerender(
      <InvoiceDetail
        invoice={invoice({ pay_by_card: true, status: "paid", amount_due: "0.00" })}
        methods={[]}
        onSubmitted={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /by card/i })).not.toBeInTheDocument();
  });

  it("keeps an invoice drafted before USD billing in rupees", () => {
    render(
      <InvoiceDetail invoice={invoice({ currency: "PKR", pkr_per_usd: null })} methods={[]} onSubmitted={vi.fn()} />,
    );

    expect(screen.getByText(/^total$/i).nextSibling).toHaveTextContent("Rs. 19,600.00");
    expect(screen.queryByText(/per USD/)).not.toBeInTheDocument();
  });
});
