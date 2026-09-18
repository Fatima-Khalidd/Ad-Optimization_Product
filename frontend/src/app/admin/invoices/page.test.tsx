import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import InvoicesPage from "./page";
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

const INVOICE: AdminInvoice = {
  id: 1,
  invoice_number: "INV-2026-0001",
  client_id: 3,
  business_name: "Acme Traders",
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  due_date: "2026-09-14",
  base_fee: "15000.00",
  suggested_recovered_waste: "23000.00",
  confirmed_recovered_waste: "23000.00",
  performance_fee: "4600.50",
  total: "19600.50",
  amount_paid: "0.00",
  status: "draft",
  confirmed_by: null,
  issued_at: null,
  created_at: "2026-09-01T00:00:00Z",
};

describe("InvoicesPage", () => {
  it("shows exact two-decimal money figures and the client's business name", async () => {
    vi.mocked(apiFetch).mockImplementation((path: string) => {
      if (path === "/api/admin/clients") return Promise.resolve(CLIENTS);
      if (path === "/api/admin/invoices") return Promise.resolve([INVOICE]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });

    render(<InvoicesPage />);

    await waitFor(() => expect(screen.getByText("INV-2026-0001")).toBeInTheDocument());

    // F6: the client's business name is a column, not just a number.
    expect(screen.getAllByText("Acme Traders").length).toBeGreaterThan(0);

    // F2: performance fee 4600.50 must render with cents, never rounded to Rs. 4,601.
    expect(screen.getByText("Rs. 4,600.50")).toBeInTheDocument();
    expect(screen.getByText("Rs. 19,600.50")).toBeInTheDocument();
  });
});
