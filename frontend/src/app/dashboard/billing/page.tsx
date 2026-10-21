"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import InvoiceDetail from "@/components/billing/InvoiceDetail";
import InvoiceTable from "@/components/billing/InvoiceTable";
import { apiFetch } from "@/lib/api";
import type { Invoice, PaymentMethod } from "@/lib/types";

export default function BillingPage() {
  // useSearchParams needs a Suspense boundary, or the page cannot be prerendered.
  return (
    <Suspense>
      <Billing />
    </Suspense>
  );
}

function Billing() {
  // The card checkout sends the client back here with ?paid=<invoice id>.
  const paidId = Number(useSearchParams().get("paid")) || null;
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(paidId);
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Plain (non-async) functions that resolve their own promise chain — an async
  // function that awaits then calls setState trips the set-state-in-effect lint
  // rule when invoked straight from a useEffect body, so the loading and error
  // handling happen inside .then()/.catch() instead of after an `await`.
  const loadList = useCallback(() => {
    return Promise.all([
      apiFetch<Invoice[]>("/api/billing/invoices"),
      apiFetch<PaymentMethod[]>("/api/billing/payment-methods"),
    ])
      .then(([rows, paymentMethods]) => {
        setInvoices(rows);
        setMethods(paymentMethods);
        setSelectedId((current) => current ?? rows[0]?.id ?? null);
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load your invoices.");
      });
  }, []);

  const loadSelected = useCallback(() => {
    const fetched =
      selectedId === null ? Promise.resolve(null) : apiFetch<Invoice>(`/api/billing/invoices/${selectedId}`);
    return fetched.then(setSelected);
  }, [selectedId]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadSelected();
  }, [loadSelected]);

  const refresh = useCallback(() => {
    return loadList().then(loadSelected);
  }, [loadList, loadSelected]);

  return (
    <main className="mx-auto grid max-w-5xl gap-8 px-4 py-8">
      <h1 className="font-display text-2xl">Billing</h1>
      {error ? (
        <p role="alert" className="text-coral">
          {error}
        </p>
      ) : null}
      {paidId !== null ? (
        <p role="status" className="rounded border border-teal/40 bg-teal/10 px-4 py-3 text-sm">
          Thank you — your card payment went through. The invoice shows as paid once the payment
          provider confirms it, usually within a minute.
        </p>
      ) : null}
      <InvoiceTable invoices={invoices} selectedId={selectedId} onSelect={setSelectedId} />
      {selected ? <InvoiceDetail invoice={selected} methods={methods} onSubmitted={refresh} /> : null}
      <p className="mt-10 text-xs text-slate">
        Paying an invoice means you accept our{" "}
        <Link href="/terms" className="underline hover:text-teal">
          Terms
        </Link>
        ,{" "}
        <Link href="/privacy" className="underline hover:text-teal">
          Privacy Policy
        </Link>{" "}
        and{" "}
        <Link href="/refunds" className="underline hover:text-teal">
          Refund Policy
        </Link>
        .
      </p>
    </main>
  );
}
