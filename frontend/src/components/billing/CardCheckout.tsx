"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";

type Props = {
  invoiceId: number;
  /** What is still owed, already formatted ("$81.67"). */
  amount: string;
};

/**
 * Sends the client to the gateway's hosted checkout. The invoice is marked paid by the
 * gateway's webhook afterwards, not by anything on this page.
 */
export default function CardCheckout({ invoiceId, amount }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startCheckout() {
    setBusy(true);
    setError(null);
    try {
      const { url } = await apiFetch<{ url: string }>(`/api/billing/invoices/${invoiceId}/checkout`, {
        method: "POST",
      });
      window.location.assign(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not start the card payment.");
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-2">
      <button
        type="button"
        onClick={startCheckout}
        disabled={busy}
        className="justify-self-start rounded bg-teal px-4 py-2 text-sm font-medium text-ink hover:bg-teal/90 disabled:opacity-60"
      >
        {busy ? "Opening secure checkout…" : `Pay ${amount} by card`}
      </button>
      <p className="text-xs text-slate">Visa, Mastercard and other cards, in US dollars. Confirmed automatically.</p>
      {error ? (
        <p role="alert" className="text-sm text-coral">
          {error}
        </p>
      ) : null}
    </div>
  );
}
