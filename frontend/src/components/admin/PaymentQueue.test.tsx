import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PaymentQueue from "./PaymentQueue";
import { apiFetch } from "@/lib/api";
import type { AdminPayment } from "@/lib/types";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

const PAYMENT: AdminPayment = {
  id: 42,
  method_type: "raast",
  transaction_ref: "JC-90002",
  amount: "9600.00",
  paid_at: "2026-08-05",
  status: "pending",
  review_note: null,
  reviewed_at: null,
  created_at: "2026-08-05T00:00:00Z",
  has_proof: true,
  client_id: 3,
  business_name: "Acme Traders",
  invoice_id: 7,
  invoice_number: "INV-2026-0001",
  invoice_total: "9600.00",
  invoice_due_date: "2026-08-14",
  invoice_status: "payment_submitted",
  invoice_is_overdue: false,
};

describe("PaymentQueue", () => {
  it("links the proof to the payment's proof route", () => {
    render(<PaymentQueue payments={[PAYMENT]} onReviewed={vi.fn()} />);

    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute(
      "href",
      "/api/admin/payments/42/proof",
    );
  });

  it("confirms a payment without requiring a note", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const onReviewed = vi.fn();
    render(<PaymentQueue payments={[PAYMENT]} onReviewed={onReviewed} />);

    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/admin/payments/42/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: null }),
      }),
    );
    await waitFor(() => expect(onReviewed).toHaveBeenCalledOnce());
  });

  it("sends the typed note when rejecting, and refuses to reject without one", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const onReviewed = vi.fn();
    render(<PaymentQueue payments={[PAYMENT]} onReviewed={onReviewed} />);

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(apiFetch).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/say why/i);

    fireEvent.change(screen.getByLabelText("Note for JC-90002"), {
      target: { value: "transaction ID does not match our records" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/admin/payments/42/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "transaction ID does not match our records" }),
      }),
    );
    await waitFor(() => expect(onReviewed).toHaveBeenCalledOnce());
  });

  it("shows the empty state when nothing is pending", () => {
    render(<PaymentQueue payments={[]} onReviewed={vi.fn()} />);
    expect(screen.getByText(/nothing waiting/i)).toBeInTheDocument();
  });
});
