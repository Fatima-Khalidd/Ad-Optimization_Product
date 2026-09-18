"use client";

import { useState } from "react";

import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import { METHOD_LABELS } from "@/lib/billing";
import { formatPKRExact } from "@/lib/format";
import type { AdminPayment } from "@/lib/types";

type Props = {
  payments: AdminPayment[];
  onReviewed: () => void;
};

export default function PaymentQueue({ payments, onReviewed }: Props) {
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function review(payment: AdminPayment, decision: "confirm" | "reject") {
    const note = (notes[payment.id] ?? "").trim();
    if (decision === "reject" && !note) {
      setError(`Say why you are rejecting ${payment.transaction_ref} — the client reads this note.`);
      return;
    }
    setBusyId(payment.id);
    setError(null);
    try {
      await apiFetch(`/api/admin/payments/${payment.id}/${decision}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: note || null }),
      });
      setNotes((current) => ({ ...current, [payment.id]: "" }));
      onReviewed();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not record that decision.");
    } finally {
      setBusyId(null);
    }
  }

  if (payments.length === 0) {
    return <p className="text-slate">Nothing waiting. Every reported payment has been reviewed.</p>;
  }

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="text-coral">
          {error}
        </p>
      )}
      <Table>
        <thead>
          <tr>
            <Th>Client</Th>
            <Th>Invoice</Th>
            <Th>Method / transaction ID</Th>
            <Th align="right">Amount</Th>
            <Th>Paid</Th>
            <Th>Proof</Th>
            <Th>Decision</Th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => (
            <tr key={payment.id}>
              <Td>{payment.business_name}</Td>
              <Td>
                <span className="tabular-nums">{payment.invoice_number}</span>
                <br />
                <span className="text-xs text-slate">
                  {formatPKRExact(payment.invoice_total)} · due {payment.invoice_due_date}
                </span>
                {payment.invoice_is_overdue ? (
                  <span className="ml-2 rounded-full bg-coral/20 px-2 py-0.5 text-xs text-coral">Overdue</span>
                ) : null}
              </Td>
              <Td>
                {METHOD_LABELS[payment.method_type]}
                <br />
                <span className="tabular-nums">{payment.transaction_ref}</span>
              </Td>
              <Td align="right">{formatPKRExact(payment.amount)}</Td>
              <Td>{payment.paid_at}</Td>
              <Td>
                {payment.has_proof ? (
                  <a
                    href={`/api/admin/payments/${payment.id}/proof`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-teal underline"
                  >
                    View
                  </a>
                ) : (
                  <span className="text-slate">—</span>
                )}
              </Td>
              <Td>
                <div className="flex flex-col gap-1">
                  <input
                    aria-label={`Note for ${payment.transaction_ref}`}
                    placeholder="Note (required to reject)"
                    className="border border-white/15 bg-surface px-1 py-0.5"
                    value={notes[payment.id] ?? ""}
                    onChange={(event) =>
                      setNotes((current) => ({ ...current, [payment.id]: event.target.value }))
                    }
                  />
                  <div className="flex gap-1">
                    <button
                      type="button"
                      disabled={busyId === payment.id}
                      onClick={() => review(payment, "confirm")}
                      className="border border-teal px-2 py-0.5 text-teal disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Confirm
                    </button>
                    <button
                      type="button"
                      disabled={busyId === payment.id}
                      onClick={() => review(payment, "reject")}
                      className="border border-coral px-2 py-0.5 text-coral disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
