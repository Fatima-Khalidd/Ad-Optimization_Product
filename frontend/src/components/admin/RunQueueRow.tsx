"use client";

import { useState } from "react";

import { Td } from "@/components/admin/Table";
import { formatPKR } from "@/lib/format";
import type { AdminRun } from "@/lib/admin-types";

export default function RunQueueRow({
  run,
  expanded,
  busy = false,
  onToggle,
  onApprove,
  onReject,
  onRequeue,
}: {
  run: AdminRun;
  expanded: boolean;
  busy?: boolean;
  onToggle: () => void;
  onApprove: (note: string) => void;
  onReject: (note: string) => void;
  onRequeue: () => void;
}) {
  const [note, setNote] = useState("");

  return (
    <>
      <tr>
        <Td>
          <button type="button" onClick={onToggle} className="underline">
            {expanded ? "−" : "+"} #{run.id}
          </button>
        </Td>
        <Td>{run.business_name}</Td>
        <Td>{run.created_at.slice(0, 10)}</Td>
        <Td>{run.status}</Td>
        <Td align="right">{formatPKR(run.headline_waste)}</Td>
        <Td align="right">{run.flagged_segments.length}</Td>
        <Td>{run.review_status}</Td>
      </tr>
      {expanded && (
        <tr>
          <Td>{null}</Td>
          <td colSpan={6} className="border-b border-white/10 px-3 py-3">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h3 className="mb-1 font-display text-sm">Waste per dimension</h3>
                <ul className="space-y-0.5 text-sm">
                  {run.dimensions.map((d) => (
                    <li
                      key={d.dimension}
                      data-testid={`dimension-${d.dimension}`}
                      className="flex justify-between border-b border-white/10 py-0.5"
                    >
                      <span>{d.dimension}</span>
                      <span className="tabular-nums">
                        {formatPKR(d.total_wasted_spend)} of {formatPKR(d.total_spend)}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs text-slate">
                  Headline waste is the largest single dimension — dimensions are never added up.
                </p>
              </div>

              <div>
                <h3 className="mb-1 font-display text-sm">Flagged segments</h3>
                <ul className="space-y-0.5 text-sm">
                  {run.flagged_segments.map((s) => (
                    <li
                      key={`${s.dimension}:${s.segment_value}`}
                      className="flex justify-between border-b border-white/10 py-0.5"
                    >
                      <span className="text-coral">{s.segment_value}</span>
                      <span className="tabular-nums">
                        {formatPKR(s.wasted_spend)} wasted · {s.conversions} conv
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="md:col-span-2">
                <h3 className="mb-1 font-display text-sm">Config snapshot</h3>
                <pre className="overflow-x-auto border border-white/15 bg-surface p-2 font-mono text-xs">
                  {JSON.stringify(run.config_snapshot, null, 2)}
                </pre>
              </div>

              {run.status === "running" && (
                <div className="md:col-span-2">
                  <p className="mb-1 text-xs text-slate">
                    Stuck in &ldquo;running&rdquo; for a while? A crashed worker can leave a
                    run here forever. Re-queuing only works once the run is genuinely stale.
                  </p>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={onRequeue}
                    className="border border-teal px-3 py-1 text-teal disabled:opacity-50"
                  >
                    Re-queue
                  </button>
                </div>
              )}

              {run.review_status === "pending" ? (
                <div className="flex flex-wrap items-end gap-2 md:col-span-2">
                  <label className="flex-1">
                    <span className="block text-xs uppercase tracking-wide text-slate">
                      Review note
                    </span>
                    <input
                      aria-label="Review note"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      className="mt-1 w-full border border-white/15 bg-surface px-2 py-1"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onApprove(note)}
                    className="border border-teal px-3 py-1 text-teal disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onReject(note)}
                    className="border border-coral px-3 py-1 text-coral disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              ) : (
                <p className="text-sm text-slate md:col-span-2">
                  <span>{run.review_status}</span> — <span>{run.review_note ?? "no note"}</span>
                </p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
