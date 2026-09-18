import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn().mockResolvedValue({ id: 11, status: "pending" }),
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

import { apiFetch } from "@/lib/api";
import PaymentForm from "@/components/billing/PaymentForm";
import type { PaymentMethod } from "@/lib/types";

const METHODS: PaymentMethod[] = [
  {
    id: 1,
    type: "jazzcash",
    account_title: "Ali Raza",
    account_identifier: "0300-1234567",
    instructions: null,
    is_active: true,
    sort_order: 0,
  },
  {
    id: 2,
    type: "raast",
    account_title: "Ali Raza",
    account_identifier: "PK36SCBL0000001123456702",
    instructions: null,
    is_active: true,
    sort_order: 1,
  },
];

function lastCall() {
  const mock = vi.mocked(apiFetch);
  return mock.mock.calls[mock.mock.calls.length - 1];
}

describe("PaymentForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockClear();
  });

  it("posts the transaction ID as multipart FormData to the invoice's payments route", async () => {
    const user = userEvent.setup();
    const onSubmitted = vi.fn();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={onSubmitted} />);

    await user.selectOptions(screen.getByLabelText(/payment method/i), "raast");
    await user.clear(screen.getByLabelText(/transaction id/i));
    await user.type(screen.getByLabelText(/transaction id/i), "JC-90002");
    await user.clear(screen.getByLabelText(/amount/i));
    await user.type(screen.getByLabelText(/amount/i), "9600");
    await user.clear(screen.getByLabelText(/payment date/i));
    await user.type(screen.getByLabelText(/payment date/i), "2026-10-05");
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    const [path, init] = lastCall();
    expect(path).toBe("/api/billing/invoices/7/payments");
    expect(init?.method).toBe("POST");
    const body = init?.body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("method_type")).toBe("raast");
    expect(body.get("transaction_ref")).toBe("JC-90002");
    expect(body.get("amount")).toBe("9600");
    expect(body.get("paid_at")).toBe("2026-10-05");
    expect(body.get("proof")).toBeNull();
    expect(onSubmitted).toHaveBeenCalledOnce();
  });

  it("attaches the screenshot when one is chosen", async () => {
    const user = userEvent.setup();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "proof.png", { type: "image/png" });

    await user.type(screen.getByLabelText(/transaction id/i), "JC-90003");
    await user.upload(screen.getByLabelText(/screenshot/i), file);
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    const body = lastCall()[1]?.body as FormData;
    expect((body.get("proof") as File).name).toBe("proof.png");
  });

  it("defaults the amount to what is still owed and refuses an empty transaction id", async () => {
    const user = userEvent.setup();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);

    expect(screen.getByLabelText(/amount/i)).toHaveValue(9600);

    await user.click(screen.getByRole("button", { name: /submit payment/i }));
    expect(apiFetch).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/transaction id/i);
  });

  it("shows the server's reason when the transaction id was already used", async () => {
    const user = userEvent.setup();
    vi.mocked(apiFetch).mockRejectedValueOnce(
      Object.assign(new Error("this transaction id has already been submitted for this payment method"), {
        status: 409,
      }),
    );
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);

    await user.type(screen.getByLabelText(/transaction id/i), "JC-90001");
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/already been submitted/i);
  });

  it("rejects an oversize proof before uploading, without calling the API", async () => {
    const user = userEvent.setup();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "big.png", { type: "image/png" });

    await user.type(screen.getByLabelText(/transaction id/i), "JC-90004");
    await user.upload(screen.getByLabelText(/screenshot/i), big);
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    expect(apiFetch).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/5 ?mb/i);
  });

  it("rejects a proof that is not PNG, JPEG or PDF before uploading, without calling the API", async () => {
    const user = userEvent.setup();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);
    const wrong = new File([new Uint8Array([1, 2, 3])], "proof.gif", { type: "image/gif" });

    await user.type(screen.getByLabelText(/transaction id/i), "JC-90005");
    // fireEvent.change (not user.upload) — user-event's upload() silently filters files
    // against the input's own `accept` attribute before firing change, so a genuinely
    // mismatched file never reaches our onChange handler that way; fireEvent bypasses
    // that browser-level gatekeeping the same way a manipulated/legacy client could.
    fireEvent.change(screen.getByLabelText(/screenshot/i), { target: { files: [wrong] } });
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    expect(apiFetch).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/png|jpeg|pdf/i);
  });
});
