import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import InvoiceForm from "./InvoiceForm";
import { apiFetch } from "@/lib/api";
import type { AdminClient, AdminInvoice } from "@/lib/admin-types";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

const CLIENTS: AdminClient[] = [
  {
    id: 3,
    business_name: "Acme Traders",
    contact_info: null,
    pricing_model: "hybrid",
    base_fee: "15000.00",
    performance_fee_pct: "20.00",
    config_overrides: {},
    created_at: "2026-07-01T00:00:00Z",
  },
];

const DRAFT: AdminInvoice = {
  id: 1,
  invoice_number: "INV-2026-0001",
  client_id: 3,
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  due_date: "2026-09-14",
  base_fee: "15000.00",
  suggested_recovered_waste: "23000.00",
  confirmed_recovered_waste: "0.00",
  performance_fee: "4600.00",
  total: "19600.00",
  amount_paid: "0.00",
  status: "draft",
  confirmed_by: null,
  issued_at: null,
  created_at: "2026-09-01T00:00:00Z",
};

// vitest.config.ts sets restoreMocks: true, so every mock (including this one)
// already gets its calls and implementation cleared before each test; an
// explicit mockReset() in a beforeEach here double-resets the same mock
// object and races with React's async event-handler catch, which is what
// caused this suite to fail with an unhandled "boom" instead of a clean
// assertion failure.
describe("InvoiceForm", () => {
  it("posts the selected client and period, then hands the draft back", async () => {
    vi.mocked(apiFetch).mockResolvedValue(DRAFT);
    const onCreated = vi.fn();
    render(<InvoiceForm clients={CLIENTS} onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText("Client"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2026-08-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft invoice" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(apiFetch).toHaveBeenCalledWith("/api/admin/invoices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: 3,
        period_start: "2026-08-01",
        period_end: "2026-08-31",
      }),
    });
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(DRAFT));
  });

  it("shows the server's message when drafting conflicts", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new Error("invoice INV-2026-0001 already covers 2026-08-01 to 2026-08-31"));
    render(<InvoiceForm clients={CLIENTS} onCreated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2026-08-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft invoice" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already covers");
  });
});
