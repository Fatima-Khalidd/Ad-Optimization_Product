"use client";

import StatusPill from "@/components/billing/StatusPill";
import { isOverdue } from "@/lib/billing";
import { formatPKRExact } from "@/lib/format";
import type { Invoice } from "@/lib/types";

type Props = {
  invoices: Invoice[];
  selectedId: number | null;
  onSelect: (id: number) => void;
};

export default function InvoiceTable({ invoices, selectedId, onSelect }: Props) {
  const today = new Date();
  if (invoices.length === 0) {
    return <p className="text-slate">No invoices yet. Your first one arrives after your first full month.</p>;
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="text-slate">
        <tr className="border-b border-slate/30">
          <th className="py-2 font-normal">Invoice</th>
          <th className="py-2 font-normal">Period</th>
          <th className="py-2 font-normal">Due</th>
          <th className="py-2 text-right font-normal">Total</th>
          <th className="py-2 text-right font-normal">Outstanding</th>
          <th className="py-2 font-normal">Status</th>
        </tr>
      </thead>
      <tbody>
        {invoices.map((invoice) => (
          <tr
            key={invoice.id}
            onClick={() => onSelect(invoice.id)}
            className={`cursor-pointer border-b border-slate/15 hover:bg-surface ${
              invoice.id === selectedId ? "bg-surface" : ""
            }`}
          >
            <td className="py-2 numeral">{invoice.invoice_number}</td>
            <td className="py-2">
              {invoice.period_start} → {invoice.period_end}
            </td>
            <td className="py-2">
              {invoice.due_date}
              {isOverdue(invoice, today) ? (
                <span className="ml-2 rounded-full bg-coral/20 px-2 py-0.5 text-xs text-coral">Overdue</span>
              ) : null}
            </td>
            <td className="py-2 text-right numeral">{formatPKRExact(invoice.total)}</td>
            <td className="py-2 text-right numeral">{formatPKRExact(invoice.amount_due)}</td>
            <td className="py-2">
              <StatusPill status={invoice.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
