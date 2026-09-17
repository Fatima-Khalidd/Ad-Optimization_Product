import SummaryNumbers from "@/components/dashboard/SummaryNumbers";
import Hero from "@/components/hero/Hero";
import RecommendationList from "@/components/recommendations/RecommendationList";
import SegmentTable from "@/components/tables/SegmentTable";
import type { ReportOut } from "@/lib/types";

type Props = { report: ReportOut; hero?: boolean };

/**
 * `generated_at` may be a naive datetime (SQLite/dev — no trailing "Z" or
 * offset) or an offset-aware one (Postgres/prod). `new Date()` parses both,
 * but a naive string without a "Z"/offset is ambiguous in some engines, so a
 * bare "YYYY-MM-DDTHH:mm:ss" is treated as UTC explicitly. Never render
 * "Invalid Date" — fall back to the raw string.
 */
function formatGeneratedAt(value: string): string {
  const hasZoneInfo = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
  const normalized = hasZoneInfo ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/**
 * The whole client-facing report. Stage 6's admin views render this with
 * hero={false}: same numbers, same tables, no animation at all.
 */
export default function ReportView({ report, hero = true }: Props) {
  const benchmarkMode = String(report.config_snapshot.benchmark_mode ?? "account_avg");

  return (
    <div>
      <section
        className="grid grid-cols-1 items-center gap-10 lg:min-h-[60vh] lg:grid-cols-[3fr_2fr] lg:gap-16"
        data-testid="hero-band"
      >
        {hero ? (
          <div className="order-2 min-h-[260px] sm:min-h-[340px] lg:order-1 lg:min-h-[440px]">
            <Hero headlineWaste={report.headline_waste} totalSpend={report.total_spend} />
          </div>
        ) : null}
        <div className={hero ? "order-1 lg:order-2" : "lg:col-span-2"}>
          <SummaryNumbers
            animate={hero}
            headlineWaste={report.headline_waste}
            recoveryPct={report.recovery_pct}
            totalSpend={report.total_spend}
          />
        </div>
      </section>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-slate/20 pt-6 text-sm text-slate">
        <p>
          Run #{report.run_id} · {report.date_range_start ?? "start unknown"} to{" "}
          {report.date_range_end ?? "end unknown"}
          <span className="block text-xs">Generated {formatGeneratedAt(report.generated_at)}</span>
        </p>
        <a
          className="text-teal underline underline-offset-4"
          href={`/api/reports/${report.run_id}/pdf`}
        >
          Download PDF
        </a>
      </div>

      <div className="mt-16">
        <SegmentTable dimensions={report.dimensions} />
      </div>

      <section aria-labelledby="recommendations-heading" className="mt-20">
        <h2 className="font-display text-2xl" id="recommendations-heading">
          What to cut first
        </h2>
        <RecommendationList recommendations={report.recommendations} />
      </section>

      <p className="mt-16 max-w-2xl text-xs text-slate">
        Waste is the spend above what these conversions should have cost, measured against the {benchmarkMode}{" "}
        benchmark. Figures are never added up across breakdowns — the headline is the largest single
        breakdown, so nothing is counted twice.
      </p>
    </div>
  );
}
