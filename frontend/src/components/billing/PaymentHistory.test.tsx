import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PaymentHistory from "@/components/billing/PaymentHistory";
import type { Payment } from "@/lib/types";

function payment(overrides: Partial<Payment> = {}): Payment {
  return {
    id: 1,
    method_type: "jazzcash",
    transaction_ref: "JC-1",
    amount: "9600.00",
    paid_at: "2026-08-05",
    status: "pending",
    review_note: null,
    reviewed_at: null,
    created_at: "2026-08-05T00:00:00Z",
    has_proof: false,
    ...overrides,
  };
}

describe("PaymentHistory", () => {
  it("shows a rejected payment's review note so the client knows what to fix", () => {
    render(
      <PaymentHistory
        payments={[payment({ status: "rejected", review_note: "transaction ID does not match our records" })]}
      />,
    );

    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText(/does not match our records/i)).toBeInTheDocument();
  });

  it("never labels a pending payment as paid or confirmed", () => {
    render(<PaymentHistory payments={[payment({ status: "pending" })]} />);

    expect(screen.getByText("Awaiting review")).toBeInTheDocument();
    expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
    expect(screen.getByText(/awaiting our check/i)).toBeInTheDocument();
  });

  it("shows the empty state with no payments", () => {
    render(<PaymentHistory payments={[]} />);
    expect(screen.getByText(/no payments reported yet/i)).toBeInTheDocument();
  });
});
