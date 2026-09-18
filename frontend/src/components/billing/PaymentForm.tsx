"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";
import { METHOD_LABELS } from "@/lib/billing";
import type { Payment, PaymentMethod } from "@/lib/types";

type Props = {
  invoiceId: number;
  methods: PaymentMethod[];
  defaultAmount: number;
  onSubmitted: () => void;
};

const FIELD =
  "w-full rounded border border-slate/40 bg-ink px-3 py-2 text-paper focus:border-teal focus:outline-none";

const MAX_PROOF_BYTES = 5 * 1024 * 1024;
const ALLOWED_PROOF_TYPES = ["image/png", "image/jpeg", "application/pdf"];

export default function PaymentForm({ invoiceId, methods, defaultAmount, onSubmitted }: Props) {
  const [methodType, setMethodType] = useState(methods[0]?.type ?? "jazzcash");
  const [transactionRef, setTransactionRef] = useState("");
  const [amount, setAmount] = useState(String(defaultAmount));
  const [paidAt, setPaidAt] = useState("");
  const [proof, setProof] = useState<File | null>(null);
  const [proofRejected, setProofRejected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function handleFile(file: File | null) {
    setError(null);
    if (file === null) {
      setProof(null);
      setProofRejected(false);
      return;
    }
    if (!ALLOWED_PROOF_TYPES.includes(file.type)) {
      setError("Proof must be a PNG, JPEG or PDF file.");
      setProof(null);
      setProofRejected(true);
      return;
    }
    if (file.size > MAX_PROOF_BYTES) {
      setError("Proof must be 5 MB or smaller.");
      setProof(null);
      setProofRejected(true);
      return;
    }
    setProof(file);
    setProofRejected(false);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // A proof rejected at selection time (wrong type or too large) must block
    // submission even though `proof` itself was cleared back to null — otherwise
    // the form would silently submit without the rejected file and without proof.
    if (proofRejected) {
      return;
    }
    if (!transactionRef.trim()) {
      setError("Enter the transaction ID from your payment app.");
      return;
    }
    const form = new FormData();
    form.set("method_type", methodType);
    form.set("transaction_ref", transactionRef.trim());
    form.set("amount", amount);
    form.set("paid_at", paidAt);
    if (proof) form.set("proof", proof);

    setBusy(true);
    setError(null);
    try {
      await apiFetch<Payment>(`/api/billing/invoices/${invoiceId}/payments`, {
        method: "POST",
        body: form,
      });
      setTransactionRef("");
      setProof(null);
      onSubmitted();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not submit this payment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3" noValidate>
      <h3 className="font-display text-lg">I have paid — record my transaction ID</h3>
      <p className="text-xs text-slate">
        This tells us you have paid. The invoice stays unpaid until we check the transaction and confirm it —
        it will not show as paid right away.
      </p>

      <label className="grid gap-1 text-sm">
        <span className="text-slate">Payment method</span>
        <select
          className={FIELD}
          value={methodType}
          onChange={(event) => setMethodType(event.target.value as PaymentMethod["type"])}
        >
          {methods.map((method) => (
            <option key={method.id} value={method.type}>
              {METHOD_LABELS[method.type]} — {method.account_identifier}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1 text-sm">
        <span className="text-slate">Transaction ID</span>
        <input
          className={FIELD}
          value={transactionRef}
          onChange={(event) => setTransactionRef(event.target.value)}
          maxLength={80}
        />
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">
          <span className="text-slate">Amount (PKR)</span>
          <input
            className={FIELD}
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-slate">Payment date</span>
          <input
            className={FIELD}
            type="date"
            value={paidAt}
            onChange={(event) => setPaidAt(event.target.value)}
          />
        </label>
      </div>

      <label className="grid gap-1 text-sm">
        <span className="text-slate">Screenshot or receipt (optional, PNG/JPEG/PDF, max 5 MB)</span>
        <input
          className={FIELD}
          type="file"
          accept="image/png,image/jpeg,application/pdf"
          onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
        />
      </label>

      {error ? (
        <p role="alert" className="text-sm text-coral">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy}
        className="justify-self-start rounded bg-teal px-4 py-2 font-medium text-ink disabled:opacity-50"
      >
        {busy ? "Submitting…" : "Submit payment"}
      </button>
      <p className="text-xs text-slate">
        We confirm every payment by hand. The invoice stays open until we have checked it.
      </p>
    </form>
  );
}
