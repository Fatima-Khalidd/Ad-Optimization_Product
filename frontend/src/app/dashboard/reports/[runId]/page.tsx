import { notFound } from "next/navigation";

import ReportView from "@/components/dashboard/ReportView";
import { getReport } from "@/lib/server-api";

export const metadata = { title: "Report · Ad Spend Optimization" };

// Next 16: route params arrive as a Promise.
export default async function RunReportPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const report = await getReport(runId);

  // The backend answers 404 for another tenant's run AND for an unapproved one,
  // so this single branch covers both (docs/PLAN.md §4 "Tenant isolation").
  // A non-404 failure also falls through to notFound() here — this page has no
  // separate error state, and never reveals whether the run exists.
  if (report === null) {
    notFound();
  }

  return <ReportView report={report} />;
}
