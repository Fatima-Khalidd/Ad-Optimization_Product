import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import SegmentTable from "./SegmentTable";
import type { DimensionOut, SegmentOut } from "@/lib/types";

// Money fields on SegmentOut/DimensionOut are decimal STRINGS on the wire
// (INTERFACES.md "Stage 3 close-out" #2) — never plain numbers. ctr/cvr are
// always a number (0.0, never null) even when their denominator is zero;
// the dash-vs-zero distinction is the component's job, not the type's.
function segment(overrides: Partial<SegmentOut> & { segment: string }): SegmentOut {
  return {
    spend: "0",
    impressions: 0,
    clicks: 0,
    conversions: 0,
    revenue: "0",
    cpa: null,
    ctr: 0,
    cvr: 0,
    roas: null,
    is_significant: true,
    is_flagged: false,
    wasted_spend: "0",
    flag_reason: null,
    ...overrides,
  };
}

const dimensions: DimensionOut[] = [
  {
    dimension: "placement",
    benchmark_cpa: "800",
    total_spend: "100000",
    total_wasted_spend: "52000",
    segments: [
      segment({
        segment: "audience_network",
        spend: "84000",
        impressions: 200000,
        clicks: 4000,
        conversions: 40,
        cpa: "2100",
        ctr: 0.02,
        cvr: 0.01,
        is_flagged: true,
        wasted_spend: "52000",
        flag_reason: "high_cpa",
      }),
      segment({
        segment: "feed",
        spend: "15000",
        impressions: 90000,
        clicks: 3600,
        conversions: 30,
        cpa: "500",
        ctr: 0.04,
        cvr: 0.008333,
      }),
      segment({
        segment: "reels",
        spend: "1000",
        impressions: 0,
        clicks: 0,
        conversions: 0,
        is_significant: false,
      }),
    ],
  },
  {
    dimension: "age_group",
    benchmark_cpa: "800",
    total_spend: "100000",
    total_wasted_spend: "12000",
    segments: [
      segment({
        segment: "55-64",
        spend: "20000",
        impressions: 40000,
        clicks: 800,
        conversions: 5,
        cpa: "4000",
        ctr: 0.02,
        cvr: 0.00625,
        is_flagged: true,
        wasted_spend: "12000",
        flag_reason: "zero_conversions",
      }),
    ],
  },
  {
    dimension: "time_slot",
    benchmark_cpa: null,
    total_spend: "0",
    total_wasted_spend: "0",
    segments: [],
  },
];

describe("SegmentTable", () => {
  it("offers one tab per dimension with the first one selected", () => {
    render(<SegmentTable dimensions={dimensions} />);

    expect(screen.getAllByRole("tab")).toHaveLength(3);
    expect(screen.getByRole("tab", { name: "Placement" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Age group" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tab", { name: "Time slot" })).toBeInTheDocument();
  });

  it("shows the active dimension's segments with humanised names and PKR amounts", () => {
    render(<SegmentTable dimensions={dimensions} />);

    expect(screen.getByText("Audience Network")).toBeInTheDocument();
    expect(screen.getByText("Rs. 84,000")).toBeInTheDocument();
    expect(screen.getByText("Rs. 2,100")).toBeInTheDocument();
    expect(screen.getByText("Rs. 52,000")).toBeInTheDocument();
    expect(screen.queryByText("55-64")).not.toBeInTheDocument();
  });

  it("states the benchmark the flags were measured against", () => {
    render(<SegmentTable dimensions={dimensions} />);

    expect(screen.getByTestId("benchmark-line")).toHaveTextContent(
      "Benchmark CPA Rs. 800 · Rs. 52,000 wasted of Rs. 100,000",
    );
  });

  it("marks flagged rows in coral, mutes rows with too little data, and never flags them", () => {
    render(<SegmentTable dimensions={dimensions} />);

    const flagged = screen.getByText("Audience Network").closest("tr");
    expect(flagged).toHaveAttribute("data-flagged", "true");
    expect(flagged).toHaveAttribute("data-significant", "true");
    expect(flagged).toHaveClass("text-coral");
    expect(flagged).toHaveTextContent(/cost per conversion too high/i);

    const clean = screen.getByText("Feed").closest("tr");
    expect(clean).toHaveAttribute("data-flagged", "false");
    expect(clean).not.toHaveClass("text-coral");

    const tiny = screen.getByText("Reels").closest("tr");
    expect(tiny).toHaveAttribute("data-significant", "false");
    expect(tiny).toHaveAttribute("data-flagged", "false");
    expect(tiny).not.toHaveClass("text-coral");
    expect(tiny).toHaveClass("text-slate");
    expect(tiny).toHaveTextContent("too little data");
  });

  it("exposes the zero-conversions flag reason in plain text, not colour alone", () => {
    render(<SegmentTable dimensions={dimensions} />);
    const user = userEvent.setup();
    return user.click(screen.getByRole("tab", { name: "Age group" })).then(() => {
      const row = screen.getByText("55-64").closest("tr");
      expect(row).toHaveTextContent(/no conversions/i);
    });
  });

  it("shows a dash, not 0.0%, for CTR/CVR when the denominator is zero", () => {
    render(<SegmentTable dimensions={dimensions} />);

    const tiny = screen.getByText("Reels").closest("tr") as HTMLElement;
    // Reels has 0 impressions and 0 clicks — both ratios must read as "no data", not "0.0%".
    expect(tiny).not.toHaveTextContent("0.0%");
    expect(tiny?.textContent?.match(/—/g)?.length ?? 0).toBeGreaterThanOrEqual(2);

    const clean = screen.getByText("Feed").closest("tr") as HTMLElement;
    expect(clean).toHaveTextContent("4.0%");
  });

  it("switches dimension when a tab is clicked", async () => {
    const user = userEvent.setup();
    render(<SegmentTable dimensions={dimensions} />);

    await user.click(screen.getByRole("tab", { name: "Age group" }));

    expect(screen.getByText("55-64")).toBeInTheDocument();
    expect(screen.queryByText("Audience Network")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Age group" })).toHaveAttribute("aria-selected", "true");
  });

  it("explains an empty dimension instead of showing a bare table", async () => {
    const user = userEvent.setup();
    render(<SegmentTable dimensions={dimensions} />);

    await user.click(screen.getByRole("tab", { name: "Time slot" }));

    expect(screen.getByText(/No rows in this upload carry a time slot/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("uses hairline dividers and no zebra striping", () => {
    const { container } = render(<SegmentTable dimensions={dimensions} />);

    expect(container.querySelector("tbody")).toHaveClass("divide-y", "divide-slate/20");
    expect(container.innerHTML).not.toContain("odd:bg");
  });

  it("renders nothing when there are no dimensions at all", () => {
    const { container } = render(<SegmentTable dimensions={[]} />);

    expect(container).toBeEmptyDOMElement();
  });
});

it("wires the panel to the selected tab with aria-controls/aria-labelledby, and updates on switch", async () => {
  const user = userEvent.setup();
  render(<SegmentTable dimensions={dimensions} />);

  const placementTab = screen.getByRole("tab", { name: "Placement" });
  const panel = screen.getByRole("tabpanel");
  expect(placementTab).toHaveAttribute("id", "tab-placement");
  expect(placementTab).toHaveAttribute("aria-controls", "panel-placement");
  expect(panel).toHaveAttribute("id", "panel-placement");
  expect(panel).toHaveAttribute("aria-labelledby", "tab-placement");

  await user.click(screen.getByRole("tab", { name: "Age group" }));

  const ageTab = screen.getByRole("tab", { name: "Age group" });
  const updatedPanel = screen.getByRole("tabpanel");
  expect(ageTab).toHaveAttribute("aria-controls", "panel-age_group");
  expect(updatedPanel).toHaveAttribute("id", "panel-age_group");
  expect(updatedPanel).toHaveAttribute("aria-labelledby", "tab-age_group");
});

it("moves between tabs with the arrow keys", async () => {
  const user = userEvent.setup();
  render(<SegmentTable dimensions={dimensions} />);

  const tabs = screen.getAllByRole("tab");
  expect(tabs[0]).toHaveAttribute("aria-selected", "true");
  expect(tabs[1]).toHaveAttribute("tabindex", "-1");

  tabs[0].focus();
  await user.keyboard("{ArrowRight}");
  expect(screen.getAllByRole("tab")[1]).toHaveAttribute("aria-selected", "true");

  await user.keyboard("{End}");
  expect(screen.getAllByRole("tab")[2]).toHaveAttribute("aria-selected", "true");

  await user.keyboard("{ArrowRight}");
  expect(screen.getAllByRole("tab")[0]).toHaveAttribute("aria-selected", "true");
});
