import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PaymentMethodTable from "./PaymentMethodTable";
import { apiFetch } from "@/lib/api";
import type { PaymentMethod } from "@/lib/types";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

const METHOD: PaymentMethod = {
  id: 1,
  type: "jazzcash",
  account_title: "Ali Raza",
  account_identifier: "0300-1234567",
  instructions: null,
  is_active: true,
  sort_order: 0,
};

describe("PaymentMethodTable", () => {
  it("posts a new account with the form fields", async () => {
    vi.mocked(apiFetch).mockResolvedValue(METHOD);
    const onChanged = vi.fn();
    render(<PaymentMethodTable methods={[]} onChanged={onChanged} />);

    fireEvent.change(screen.getByLabelText("Method"), { target: { value: "raast" } });
    fireEvent.change(screen.getByLabelText("Account title"), { target: { value: "Ali Raza" } });
    fireEvent.change(screen.getByLabelText("Account number / IBAN"), {
      target: { value: "PK36SCBL0000001123456702" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add account" }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/admin/payment-methods", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "raast",
          account_title: "Ali Raza",
          account_identifier: "PK36SCBL0000001123456702",
          instructions: null,
          sort_order: 0,
        }),
      }),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  });

  it("toggles is_active unmistakably", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...METHOD, is_active: false });
    const onChanged = vi.fn();
    render(<PaymentMethodTable methods={[METHOD]} onChanged={onChanged} />);

    expect(screen.getByRole("button", { name: "Active" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Active" }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/admin/payment-methods/1", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: false }),
      }),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  });

  it("patches sort_order on blur when it changed", async () => {
    vi.mocked(apiFetch).mockResolvedValue(METHOD);
    render(<PaymentMethodTable methods={[METHOD]} onChanged={vi.fn()} />);

    const input = screen.getByLabelText("Sort order for 0300-1234567");
    fireEvent.change(input, { target: { value: "3" } });
    fireEvent.blur(input);

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/admin/payment-methods/1", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: 3 }),
      }),
    );
  });
});
