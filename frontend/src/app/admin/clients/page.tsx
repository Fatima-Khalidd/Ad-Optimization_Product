"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import { formatPKR } from "@/lib/format";
import type { AdminClient } from "@/lib/admin-types";

export default function ClientsPage() {
  const [clients, setClients] = useState<AdminClient[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AdminClient[]>("/api/admin/clients")
      .then(setClients)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p role="alert" className="text-coral">{error}</p>;
  if (!clients) return <p className="text-slate">Loading…</p>;

  return (
    <Table>
      <thead>
        <tr>
          <Th>Business</Th>
          <Th align="right">Base fee</Th>
          <Th align="right">Performance %</Th>
          <Th>Overrides</Th>
          <Th>Joined</Th>
        </tr>
      </thead>
      <tbody>
        {clients.map((client) => (
          <tr key={client.id}>
            <Td>
              <Link href={`/admin/clients/${client.id}`} className="underline">
                {client.business_name}
              </Link>
            </Td>
            <Td align="right">{formatPKR(client.base_fee)}</Td>
            <Td align="right">{Number(client.performance_fee_pct)}%</Td>
            <Td>{Object.keys(client.config_overrides).length || "—"}</Td>
            <Td>{client.created_at.slice(0, 10)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
