"use client";

import { useCallback, useEffect, useState } from "react";

import PaymentMethodTable from "@/components/admin/PaymentMethodTable";
import { apiFetch } from "@/lib/api";
import type { PaymentMethod } from "@/lib/types";

export default function AdminPaymentMethodsPage() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<PaymentMethod[]>("/api/admin/payment-methods")
      .then(setMethods)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-lg">Payment accounts</h1>
      <p className="max-w-2xl text-xs text-slate">
        These appear on every invoice and on the client billing page, lowest sort order first. Hiding an
        account keeps its history intact — it just stops appearing to clients.
      </p>
      {error && (
        <p role="alert" className="text-coral">
          {error}
        </p>
      )}
      <PaymentMethodTable methods={methods} onChanged={load} />
    </div>
  );
}
