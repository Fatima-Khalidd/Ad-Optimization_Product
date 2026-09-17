"use client";

import { useCallback, useEffect, useState } from "react";

import RunQueueRow from "@/components/admin/RunQueueRow";
import { Table, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import type { AdminRun } from "@/lib/admin-types";

const FILTERS = ["pending", "approved", "rejected", "all"] as const;
type Filter = (typeof FILTERS)[number];

export default function RunsPage() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [runs, setRuns] = useState<AdminRun[] | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const query = filter === "all" ? "" : `?review_status=${filter}`;
    apiFetch<AdminRun[]>(`/api/admin/runs${query}`)
      .then(setRuns)
      .catch((e: Error) => setError(e.message));
  }, [filter]);

  useEffect(load, [load]);

  async function review(runId: number, action: "approve" | "reject", note: string) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch<AdminRun>(`/api/admin/runs/${runId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ note: note || null }),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 text-sm">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`border px-2 py-0.5 ${
              filter === f ? "border-teal text-teal" : "border-white/15 text-slate"
            }`}
          >
            {f}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-coral">
          {error}
        </p>
      )}
      {!runs ? (
        <p className="text-slate">Loading…</p>
      ) : runs.length === 0 ? (
        <p className="text-slate">Nothing waiting for review.</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Run</Th>
              <Th>Client</Th>
              <Th>Created</Th>
              <Th>Status</Th>
              <Th align="right">Headline waste</Th>
              <Th align="right">Flagged</Th>
              <Th>Review</Th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <RunQueueRow
                key={run.id}
                run={run}
                expanded={expanded === run.id}
                busy={busy}
                onToggle={() => setExpanded(expanded === run.id ? null : run.id)}
                onApprove={(note) => review(run.id, "approve", note)}
                onReject={(note) => review(run.id, "reject", note)}
              />
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
