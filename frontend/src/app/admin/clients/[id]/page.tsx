"use client";

import { use, useEffect, useState } from "react";

import ClientEditForm from "@/components/admin/ClientEditForm";
import { apiFetch } from "@/lib/api";
import type { AdminClient } from "@/lib/admin-types";

export default function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [client, setClient] = useState<AdminClient | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AdminClient>(`/api/admin/clients/${id}`)
      .then(setClient)
      .catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) return <p role="alert" className="text-coral">{error}</p>;
  if (!client) return <p className="text-slate">Loading…</p>;

  return (
    <div className="space-y-4">
      <h1 className="font-display text-xl">{client.business_name}</h1>
      <ClientEditForm client={client} />
    </div>
  );
}
