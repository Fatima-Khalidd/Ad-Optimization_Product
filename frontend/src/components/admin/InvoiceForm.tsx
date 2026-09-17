"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import { apiFetch } from "@/lib/api";
import type { AdminClient, AdminInvoice } from "@/lib/admin-types";

export default function InvoiceForm({
  clients,
  onCreated,
}: {
  clients: AdminClient[];
  onCreated: (invoice: AdminInvoice) => void;
}) {
  const [clientId, setClientId] = useState(String(clients[0]?.id ?? ""));
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const invoice = await apiFetch<AdminInvoice>("/api/admin/invoices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: Number(clientId),
          period_start: periodStart,
          period_end: periodEnd,
        }),
      });
      onCreated(invoice);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Draft failed.");
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2 text-sm">
      <label>
        <span className="block text-xs uppercase tracking-wide text-slate">Client</span>
        <select
          aria-label="Client"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="mt-1 border border-white/15 bg-surface px-2 py-1"
        >
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.business_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="block text-xs uppercase tracking-wide text-slate">Period start</span>
        <input
          aria-label="Period start"
          type="date"
          value={periodStart}
          onChange={(e) => setPeriodStart(e.target.value)}
          className="mt-1 border border-white/15 bg-surface px-2 py-1"
        />
      </label>
      <label>
        <span className="block text-xs uppercase tracking-wide text-slate">Period end</span>
        <input
          aria-label="Period end"
          type="date"
          value={periodEnd}
          onChange={(e) => setPeriodEnd(e.target.value)}
          className="mt-1 border border-white/15 bg-surface px-2 py-1"
        />
      </label>
      <button type="submit" className="border border-teal px-3 py-1 text-teal">
        Draft invoice
      </button>
      {error && (
        <p role="alert" className="w-full text-coral">
          {error}
        </p>
      )}
    </form>
  );
}
