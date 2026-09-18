"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import { METHOD_LABELS } from "@/lib/billing";
import type { MethodType, PaymentMethod } from "@/lib/types";

const EMPTY = {
  type: "jazzcash" as MethodType,
  account_title: "",
  account_identifier: "",
  instructions: "",
  sort_order: 0,
};

const FIELD = "border border-white/15 bg-surface px-2 py-1";

export default function PaymentMethodTable({
  methods,
  onChanged,
}: {
  methods: PaymentMethod[];
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);

  async function patch(method: PaymentMethod, body: Record<string, unknown>) {
    setError(null);
    try {
      await apiFetch(`/api/admin/payment-methods/${method.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update that account.");
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await apiFetch("/api/admin/payment-methods", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...draft, instructions: draft.instructions || null }),
      });
      setDraft(EMPTY);
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add that account.");
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <p role="alert" className="text-coral">
          {error}
        </p>
      )}

      <Table>
        <thead>
          <tr>
            <Th>Method</Th>
            <Th>Account title</Th>
            <Th>Account number / IBAN</Th>
            <Th>Order</Th>
            <Th>Shown to clients</Th>
          </tr>
        </thead>
        <tbody>
          {methods.map((method) => (
            <tr key={method.id}>
              <Td>{METHOD_LABELS[method.type]}</Td>
              <Td>{method.account_title}</Td>
              <Td>
                <span className="tabular-nums">{method.account_identifier}</span>
              </Td>
              <Td>
                <input
                  aria-label={`Sort order for ${method.account_identifier}`}
                  type="number"
                  className={`${FIELD} w-16`}
                  defaultValue={method.sort_order}
                  onBlur={(event) => {
                    const next = Number(event.target.value);
                    if (next !== method.sort_order) void patch(method, { sort_order: next });
                  }}
                />
              </Td>
              <Td>
                <button
                  type="button"
                  onClick={() => patch(method, { is_active: !method.is_active })}
                  aria-pressed={method.is_active}
                  className={
                    method.is_active
                      ? "border border-teal px-2 py-0.5 text-teal"
                      : "border border-white/15 px-2 py-0.5 text-slate"
                  }
                >
                  {method.is_active ? "Active" : "Hidden"}
                </button>
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>

      <form onSubmit={create} className="flex flex-wrap items-end gap-2 text-sm">
        <label>
          <span className="block text-xs uppercase tracking-wide text-slate">Method</span>
          <select
            aria-label="Method"
            value={draft.type}
            onChange={(event) => setDraft({ ...draft, type: event.target.value as MethodType })}
            className={`${FIELD} mt-1`}
          >
            {(Object.keys(METHOD_LABELS) as MethodType[]).map((type) => (
              <option key={type} value={type}>
                {METHOD_LABELS[type]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="block text-xs uppercase tracking-wide text-slate">Account title</span>
          <input
            aria-label="Account title"
            className={`${FIELD} mt-1`}
            value={draft.account_title}
            onChange={(event) => setDraft({ ...draft, account_title: event.target.value })}
            required
          />
        </label>
        <label>
          <span className="block text-xs uppercase tracking-wide text-slate">Account number / IBAN</span>
          <input
            aria-label="Account number / IBAN"
            className={`${FIELD} mt-1`}
            value={draft.account_identifier}
            onChange={(event) => setDraft({ ...draft, account_identifier: event.target.value })}
            required
          />
        </label>
        <label>
          <span className="block text-xs uppercase tracking-wide text-slate">Sort order</span>
          <input
            aria-label="Sort order"
            className={`${FIELD} mt-1 w-16`}
            type="number"
            value={draft.sort_order}
            onChange={(event) => setDraft({ ...draft, sort_order: Number(event.target.value) })}
          />
        </label>
        <label>
          <span className="block text-xs uppercase tracking-wide text-slate">Instructions</span>
          <input
            aria-label="Instructions shown on the invoice"
            className={`${FIELD} mt-1`}
            value={draft.instructions}
            onChange={(event) => setDraft({ ...draft, instructions: event.target.value })}
          />
        </label>
        <button type="submit" className="border border-teal px-3 py-1 text-teal">
          Add account
        </button>
      </form>
    </div>
  );
}
