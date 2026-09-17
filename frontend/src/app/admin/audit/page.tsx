"use client";

import { useEffect, useState } from "react";

import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import type { AuditEntry } from "@/lib/admin-types";

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AuditEntry[]>("/api/admin/audit-log?limit=200")
      .then(setEntries)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p role="alert" className="text-coral">{error}</p>;
  if (!entries) return <p className="text-slate">Loading…</p>;

  return (
    <Table>
      <thead>
        <tr>
          <Th>When</Th>
          <Th>Actor</Th>
          <Th>Action</Th>
          <Th>Entity</Th>
          <Th>Before</Th>
          <Th>After</Th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id}>
            <Td>{entry.created_at.replace("T", " ").slice(0, 19)}</Td>
            <Td>{entry.actor_user_id ?? "—"}</Td>
            <Td>{entry.action}</Td>
            <Td>
              {entry.entity_type} #{entry.entity_id}
            </Td>
            <Td>
              <pre className="max-w-xs overflow-x-auto font-mono text-xs text-slate">
                {entry.before ? JSON.stringify(entry.before) : "—"}
              </pre>
            </Td>
            <Td>
              <pre className="max-w-xs overflow-x-auto font-mono text-xs">
                {entry.after ? JSON.stringify(entry.after) : "—"}
              </pre>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
