"use client";

import { useCallback, useEffect, useState } from "react";

import InvoiceForm from "@/components/admin/InvoiceForm";
import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import { formatPKRExact } from "@/lib/format";
import type { AdminClient, AdminInvoice } from "@/lib/admin-types";

export default function InvoicesPage() {
  const [clients, setClients] = useState<AdminClient[]>([]);
  const [invoices, setInvoices] = useState<AdminInvoice[]>([]);
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [dueDates, setDueDates] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<AdminInvoice[]>("/api/admin/invoices")
      .then(setInvoices)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    apiFetch<AdminClient[]>("/api/admin/clients")
      .then(setClients)
      .catch((e: Error) => setError(e.message));
    load();
  }, [load]);

  async function act(invoice: AdminInvoice, action: "confirm" | "issue" | "void") {
    setError(null);
    const body =
      action === "confirm"
        ? { confirmed_recovered_waste: amounts[invoice.id] ?? invoice.suggested_recovered_waste }
        : action === "issue"
          ? { due_date: dueDates[invoice.id] ?? invoice.due_date }
          : { note: "voided from the admin panel" };
    try {
      await apiFetch<AdminInvoice>(`/api/admin/invoices/${invoice.id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed.`);
    }
  }

  return (
    <div className="space-y-4">
      <InvoiceForm clients={clients} onCreated={load} />
      {error && (
        <p role="alert" className="text-coral">
          {error}
        </p>
      )}
      <p className="max-w-2xl text-xs text-slate">
        &ldquo;Suggested&rdquo; is the run&rsquo;s headline waste — the largest single
        dimension&rsquo;s recovered spend, never the sum of every dimension. The admin confirms
        the figure that actually goes on the invoice before it is issued; the fee and total below
        always reflect what the server last computed, never client-side arithmetic.
      </p>
      <Table>
        <thead>
          <tr>
            <Th>Number</Th>
            <Th>Client</Th>
            <Th>Period</Th>
            <Th align="right">Base fee</Th>
            <Th align="right">Suggested (largest dimension)</Th>
            <Th align="right">Confirmed</Th>
            <Th align="right">Performance fee</Th>
            <Th align="right">Total</Th>
            <Th>Status</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <Td>{invoice.invoice_number}</Td>
              <Td>{invoice.business_name}</Td>
              <Td>
                {invoice.period_start} → {invoice.period_end}
              </Td>
              <Td align="right">{formatPKRExact(invoice.base_fee)}</Td>
              <Td align="right">{formatPKRExact(invoice.suggested_recovered_waste)}</Td>
              <Td align="right">{formatPKRExact(invoice.confirmed_recovered_waste)}</Td>
              <Td align="right">{formatPKRExact(invoice.performance_fee)}</Td>
              <Td align="right">{formatPKRExact(invoice.total)}</Td>
              <Td>{invoice.status}</Td>
              <Td>
                {invoice.status === "draft" && (
                  <div className="flex flex-wrap items-center gap-1">
                    <input
                      aria-label={`Confirmed recovered waste for ${invoice.invoice_number}`}
                      value={amounts[invoice.id] ?? invoice.suggested_recovered_waste}
                      onChange={(e) => setAmounts({ ...amounts, [invoice.id]: e.target.value })}
                      className="w-28 border border-white/15 bg-surface px-1 py-0.5 tabular-nums"
                    />
                    <button
                      type="button"
                      onClick={() => act(invoice, "confirm")}
                      className="border border-white/25 px-2 py-0.5"
                    >
                      Confirm
                    </button>
                    <input
                      aria-label={`Due date for ${invoice.invoice_number}`}
                      type="date"
                      value={dueDates[invoice.id] ?? invoice.due_date}
                      onChange={(e) => setDueDates({ ...dueDates, [invoice.id]: e.target.value })}
                      className="border border-white/15 bg-surface px-1 py-0.5"
                    />
                    <button
                      type="button"
                      onClick={() => act(invoice, "issue")}
                      className="border border-teal px-2 py-0.5 text-teal"
                    >
                      Issue
                    </button>
                  </div>
                )}
                {invoice.status !== "void" && invoice.status !== "paid" && (
                  <button
                    type="button"
                    onClick={() => act(invoice, "void")}
                    className="mt-1 border border-coral px-2 py-0.5 text-coral"
                  >
                    Void
                  </button>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
