"use client";

import { useState } from "react";

import { formatPKR, formatPct, humanizeSegment } from "@/lib/format";
import { DIMENSION_LABELS, type DimensionOut, type SegmentOut } from "@/lib/types";

const FLAG_REASON_LABEL: Record<NonNullable<SegmentOut["flag_reason"]>, string> = {
  zero_conversions: "no conversions",
  high_cpa: "cost per conversion too high",
};

/**
 * ctr/cvr are always a number on the wire (0.0, never null) even when their
 * denominator is zero — INTERFACES.md "Stage 3 close-out" #2. A measured 0%
 * and "no data yet" must not look the same, so the dash is keyed off the
 * denominator (impressions for CTR, clicks for CVR), not off the ratio value.
 */
function formatRatioPct(ratio: number, denominator: number): string {
  if (denominator <= 0) return "—";
  return formatPct(ratio * 100);
}

/**
 * The breakdown table. Reused unchanged by Stage 6's admin panel, so it stays
 * animation-free: no transitions on rows, no hover effect, no motion.
 */
export default function SegmentTable({ dimensions }: { dimensions: DimensionOut[] }) {
  const [active, setActive] = useState(0);
  const dimension = dimensions[active];
  if (dimension === undefined) return null;

  const label = DIMENSION_LABELS[dimension.dimension];

  return (
    <section aria-labelledby="breakdown-heading">
      <h2 className="font-display text-2xl" id="breakdown-heading">
        Where the money went
      </h2>

      <div aria-label="Breakdown dimension" className="mt-6 flex flex-wrap gap-6 border-b border-slate/20" role="tablist">
        {dimensions.map((candidate, index) => (
          <button
            aria-selected={index === active}
            className={`-mb-px border-b-2 pb-3 text-sm ${
              index === active ? "border-teal text-paper" : "border-transparent text-slate"
            }`}
            key={candidate.dimension}
            onClick={() => setActive(index)}
            role="tab"
            type="button"
          >
            {DIMENSION_LABELS[candidate.dimension]}
          </button>
        ))}
      </div>

      <p className="mt-4 text-sm text-slate" data-testid="benchmark-line">
        Benchmark CPA {dimension.benchmark_cpa === null ? "—" : formatPKR(dimension.benchmark_cpa)} ·{" "}
        {formatPKR(dimension.total_wasted_spend)} wasted of {formatPKR(dimension.total_spend)}
      </p>

      {dimension.segments.length === 0 ? (
        <p className="mt-8 max-w-xl text-slate">
          No rows in this upload carry a {label.toLowerCase()} value. Ad platforms cannot always export every
          breakdown together — upload a second export with this breakdown to see it here.
        </p>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[48rem] text-sm">
            <thead>
              <tr className="border-b border-slate/20 text-left text-xs uppercase tracking-[0.14em] text-slate">
                <th className="py-3 pr-4 font-normal" scope="col">
                  {label}
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  Spend
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  Impressions
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  CTR
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  Conversions
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  CVR
                </th>
                <th className="py-3 pr-4 text-right font-normal" scope="col">
                  CPA
                </th>
                <th className="py-3 text-right font-normal" scope="col">
                  Wasted
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate/20">
              {dimension.segments.map((segment) => (
                <tr
                  className={
                    segment.is_flagged ? "text-coral" : segment.is_significant ? "text-paper" : "text-slate"
                  }
                  data-flagged={segment.is_flagged}
                  data-significant={segment.is_significant}
                  key={segment.segment}
                >
                  <td className="py-3 pr-4">
                    {humanizeSegment(segment.segment)}
                    {segment.is_flagged && segment.flag_reason !== null ? (
                      <span className="ml-2 text-[0.65rem] uppercase tracking-[0.14em]">
                        Flagged — {FLAG_REASON_LABEL[segment.flag_reason]}
                      </span>
                    ) : null}
                    {!segment.is_flagged && !segment.is_significant ? (
                      <span className="ml-2 text-[0.65rem] uppercase tracking-[0.14em]">too little data</span>
                    ) : null}
                  </td>
                  <td className="py-3 pr-4 text-right tabular-nums">{formatPKR(segment.spend)}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{segment.impressions.toLocaleString("en-US")}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">
                    {formatRatioPct(segment.ctr, segment.impressions)}
                  </td>
                  <td className="py-3 pr-4 text-right tabular-nums">{segment.conversions}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{formatRatioPct(segment.cvr, segment.clicks)}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">
                    {segment.cpa === null ? "—" : formatPKR(segment.cpa)}
                  </td>
                  <td className="py-3 text-right tabular-nums">
                    {Number(segment.wasted_spend) > 0 ? formatPKR(segment.wasted_spend) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
