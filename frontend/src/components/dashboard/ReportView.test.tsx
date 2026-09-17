import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportView from "./ReportView";
import type { ReportOut } from "@/lib/types";

// The hero is covered by Hero.test.tsx / FlowStatic.test.tsx; here we only care
// that ReportView mounts it (or does not).
vi.mock("@/components/hero/Hero", () => ({
  default: () => <div data-testid="hero" />,
}));

const report: ReportOut = {
  run_id: 5,
  upload_id: 12,
  generated_at: "2026-09-16T09:10:00Z",
  date_range_start: "2026-08-01",
  date_range_end: "2026-08-31",
  total_spend: "400000.00",
  headline_waste: "100000.00",
  recovery_pct: "25.00",
  dimensions: [
    {
      dimension: "placement",
      benchmark_cpa: "800.00",
      total_spend: "400000.00",
      total_wasted_spend: "100000.00",
      segments: [
        {
          segment: "audience_network",
          spend: "84000.00",
          impressions: 90000,
          clicks: 900,
          conversions: 40,
          revenue: "0.00",
          cpa: "2100.00",
          ctr: 0.01,
          cvr: 0.04,
          roas: null,
          is_significant: true,
          is_flagged: true,
          wasted_spend: "52000.00",
          flag_reason: "high_cpa",
        },
      ],
    },
  ],
  recommendations: [
    {
      id: 1,
      dimension: "placement",
      segment_name: "audience_network",
      current_spend: "84000.00",
      recommended_cut: "50400.00",
      reason: "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion.",
    },
  ],
  config_snapshot: { benchmark_mode: "account_avg", waste_multiplier: 1.5 },
};

describe("ReportView", () => {
  it("shows the three headline numbers as large type", () => {
    render(<ReportView report={report} />);

    expect(screen.getByText("Total spend analysed")).toBeInTheDocument();
    expect(screen.getByText("Estimated waste")).toBeInTheDocument();
    expect(screen.getByText("Recoverable share of spend")).toBeInTheDocument();
    expect(screen.getByTestId("stat-total-spend")).toHaveTextContent("Rs. 400,000");
    expect(screen.getByTestId("stat-recovery-pct")).toHaveTextContent("25.0%");
    expect(screen.getByTestId("stat-total-spend")).toHaveClass("font-display");
  });

  it("puts the hero beside the numbers in a 3fr/2fr row about 60vh tall", () => {
    render(<ReportView report={report} />);

    expect(screen.getByTestId("hero")).toBeInTheDocument();
    const band = screen.getByTestId("hero-band");
    expect(band.className).toContain("lg:grid-cols-[3fr_2fr]");
    expect(band.className).toContain("lg:min-h-[60vh]");
    expect(band.className).toContain("grid-cols-1");
  });

  it("renders the tables and the recommendations", () => {
    render(<ReportView report={report} />);

    expect(screen.getByRole("tab", { name: "Placement" })).toBeInTheDocument();
    expect(screen.getAllByText("Audience Network").length).toBeGreaterThan(0);
    expect(screen.getByText("Cut Rs. 50,400")).toBeInTheDocument();
  });

  it("links to the PDF for this run and states the date range", () => {
    render(<ReportView report={report} />);

    expect(screen.getByRole("link", { name: "Download PDF" })).toHaveAttribute("href", "/api/reports/5/pdf");
    expect(screen.getByText(/2026-08-01/)).toHaveTextContent("Run #5 · 2026-08-01 to 2026-08-31");
  });

  it("names the benchmark the numbers were measured against", () => {
    render(<ReportView report={report} />);

    expect(screen.getByText(/account_avg/)).toBeInTheDocument();
  });

  it("drops the hero entirely for admin views", () => {
    render(<ReportView hero={false} report={report} />);

    expect(screen.queryByTestId("hero")).not.toBeInTheDocument();
    expect(screen.getByTestId("stat-total-spend")).toHaveTextContent("Rs. 400,000");
    expect(screen.getByRole("tab", { name: "Placement" })).toBeInTheDocument();
  });
});
