import Link from "next/link";

import ReportView from "@/components/dashboard/ReportView";
import EmptyState from "@/components/ui/EmptyState";
import { getUploads, serverFetch } from "@/lib/server-api";
import type { ReportOut } from "@/lib/types";

export const metadata = { title: "Report · Ad Spend Optimization" };

export default async function DashboardPage() {
  // serverFetch (not the getLatestReport() helper) because the empty state and
  // a real failure must not look the same: 404/204 is "nothing approved yet"
  // (calm, expected), anything else (500, backend down) is a genuine error.
  const { status, data: report } = await serverFetch<ReportOut>("/api/reports/latest");
  if (status === 200 && report !== null) {
    return <ReportView report={report} />;
  }

  if (status !== 404 && status !== 204) {
    return (
      <EmptyState
        body="Something went wrong loading your report. Please refresh the page, or try again shortly."
        title="We couldn't load your report."
      />
    );
  }

  // No approved report. Two different empty states, and they are not the same
  // story: "you have not uploaded anything" vs "we are still checking it".
  const uploads = await getUploads();
  if (uploads.length > 0) {
    return (
      <EmptyState
        action={
          <Link className="text-teal underline underline-offset-4" href="/dashboard/upload">
            Upload another export
          </Link>
        }
        body="We review every analysis by hand before it reaches you, so the numbers on your invoice are numbers we stand behind. Your report appears here as soon as it is approved."
        title="Your analysis is with our reviewer."
      />
    );
  }

  return (
    <EmptyState
      action={
        <Link className="text-teal underline underline-offset-4" href="/dashboard/upload">
          Upload your first CSV
        </Link>
      }
      body="Export your ad data with the placement, age and time-of-day breakdowns, upload it, and we will show you which segments are burning money."
      title="Nothing to show yet."
    />
  );
}
