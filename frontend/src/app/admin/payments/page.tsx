"use client";

import { useCallback, useEffect, useState } from "react";

import PaymentQueue from "@/components/admin/PaymentQueue";
import { apiFetch } from "@/lib/api";
import type { AdminPayment } from "@/lib/types";

export default function AdminPaymentsPage() {
  const [payments, setPayments] = useState<AdminPayment[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<AdminPayment[]>(`/api/admin/payments?status=${showAll ? "all" : "pending"}`)
      .then(setPayments)
      .catch((e: Error) => setError(e.message));
  }, [showAll]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-lg">Payments</h1>
        <label className="flex items-center gap-2 text-sm text-slate">
          <input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} />
          Show reviewed payments too
        </label>
      </div>
      {error && (
        <p role="alert" className="text-coral">
          {error}
        </p>
      )}
      <PaymentQueue payments={payments} onReviewed={load} />
    </div>
  );
}
