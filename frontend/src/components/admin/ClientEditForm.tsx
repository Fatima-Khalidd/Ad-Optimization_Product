"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import { apiFetch } from "@/lib/api";
import type { AdminClient, ClientPatch } from "@/lib/admin-types";

export default function ClientEditForm({ client }: { client: AdminClient }) {
  const [baseFee, setBaseFee] = useState(client.base_fee);
  const [pct, setPct] = useState(client.performance_fee_pct);
  const [overrides, setOverrides] = useState(JSON.stringify(client.config_overrides, null, 2));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaved(false);

    let parsed: unknown;
    try {
      parsed = JSON.parse(overrides || "{}");
    } catch {
      setError("Overrides must be valid JSON.");
      return;
    }

    try {
      const body: ClientPatch = {
        base_fee: baseFee,
        performance_fee_pct: pct,
        config_overrides: parsed as Record<string, unknown>,
      };
      await apiFetch<AdminClient>(`/api/admin/clients/${client.id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setSaved(true);
    } catch (e) {
      // 422 from PipelineConfig.from_overrides: "unknown config key: typo_key"
      setError(e instanceof Error ? e.message : "Save failed.");
    }
  }

  return (
    <form onSubmit={save} className="max-w-xl space-y-3 text-sm">
      <label className="block">
        <span className="text-xs uppercase tracking-wide text-slate">Base fee (PKR)</span>
        <input
          value={baseFee}
          onChange={(e) => setBaseFee(e.target.value)}
          className="mt-1 w-full border border-white/15 bg-surface px-2 py-1 tabular-nums"
        />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-wide text-slate">Performance fee %</span>
        <input
          value={pct}
          onChange={(e) => setPct(e.target.value)}
          className="mt-1 w-full border border-white/15 bg-surface px-2 py-1 tabular-nums"
        />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-wide text-slate">
          Config overrides (JSON — keys must exist in PipelineConfig)
        </span>
        <textarea
          value={overrides}
          onChange={(e) => setOverrides(e.target.value)}
          rows={10}
          className="mt-1 w-full border border-white/15 bg-surface px-2 py-1 font-mono text-xs"
        />
      </label>
      {error && (
        <p role="alert" className="text-coral">
          {error}
        </p>
      )}
      {saved && <p className="text-teal">Saved.</p>}
      <button type="submit" className="border border-teal px-3 py-1 text-teal">
        Save
      </button>
    </form>
  );
}
