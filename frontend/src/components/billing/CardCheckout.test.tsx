import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

import CardCheckout from "@/components/billing/CardCheckout";
import { apiFetch } from "@/lib/api";

describe("CardCheckout", () => {
  const mock = vi.mocked(apiFetch);
  const assign = vi.fn();

  afterEach(() => {
    mock.mockReset();
    assign.mockReset();
    vi.unstubAllGlobals();
  });

  it("asks the server for a checkout and sends the client there", async () => {
    vi.stubGlobal("location", { ...window.location, assign });
    mock.mockResolvedValue({ url: "https://pay.example/checkout/abc" });
    render(<CardCheckout invoiceId={7} amount="$81.67" />);

    await userEvent.click(screen.getByRole("button", { name: "Pay $81.67 by card" }));

    expect(mock).toHaveBeenCalledWith("/api/billing/invoices/7/checkout", { method: "POST" });
    expect(assign).toHaveBeenCalledWith("https://pay.example/checkout/abc");
  });

  it("shows the server's reason when the checkout cannot start", async () => {
    mock.mockRejectedValue(new Error("could not start a card payment; try again shortly"));
    render(<CardCheckout invoiceId={7} amount="$81.67" />);

    await userEvent.click(screen.getByRole("button", { name: /by card/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("could not start a card payment");
    expect(screen.getByRole("button", { name: /by card/i })).toBeEnabled();
  });
});
