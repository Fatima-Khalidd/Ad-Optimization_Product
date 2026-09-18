import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";

import RunQueueRow from "./RunQueueRow";
import type { AdminRun } from "@/lib/admin-types";

const RUN: AdminRun = {
  id: 7,
  client_id: 3,
  business_name: "Acme Traders",
  upload_id: 11,
  status: "done",
  review_status: "pending",
  headline_waste: "52000.00",
  review_note: null,
  reviewed_by: null,
  reviewed_at: null,
  created_at: "2026-08-25T00:00:00Z",
  dimensions: [
    { dimension: "placement", total_spend: "100000.00", total_wasted_spend: "52000.00", benchmark_cpa: "800.00" },
    { dimension: "age_group", total_spend: "100000.00", total_wasted_spend: "12000.00", benchmark_cpa: "800.00" },
  ],
  flagged_segments: [
    { dimension: "placement", segment_value: "audience_network", spend: "84000.00", conversions: 40, cpa: "2100.00", wasted_spend: "52000.00" },
    { dimension: "age_group", segment_value: "55-64", spend: "20000.00", conversions: 5, cpa: "4000.00", wasted_spend: "12000.00" },
  ],
  config_snapshot: { benchmark_mode: "account_avg", waste_multiplier: 1.5 },
};

function renderRow(overrides: Partial<ComponentProps<typeof RunQueueRow>> = {}) {
  const props = {
    run: RUN,
    expanded: false,
    onToggle: vi.fn(),
    onApprove: vi.fn(),
    onReject: vi.fn(),
    onRequeue: vi.fn(),
    ...overrides,
  };
  render(
    <table>
      <tbody>
        <RunQueueRow {...props} />
      </tbody>
    </table>,
  );
  return props;
}

describe("RunQueueRow", () => {
  it("shows the summary line with the headline waste", () => {
    renderRow();
    expect(screen.getByText("Acme Traders")).toBeInTheDocument();
    expect(screen.getByText("Rs. 52,000")).toBeInTheDocument();
  });

  it("hides the detail until the row is expanded", () => {
    renderRow();
    expect(screen.queryByText("audience_network")).not.toBeInTheDocument();
  });

  it("renders every flagged segment and per-dimension total when expanded", () => {
    renderRow({ expanded: true });

    expect(screen.getByText("audience_network")).toBeInTheDocument();
    expect(screen.getByText("55-64")).toBeInTheDocument();
    // per-dimension totals are listed side by side, never summed
    expect(screen.getByTestId("dimension-placement")).toHaveTextContent("Rs. 52,000");
    expect(screen.getByTestId("dimension-age_group")).toHaveTextContent("Rs. 12,000");
    expect(screen.getByText(/"benchmark_mode": "account_avg"/)).toBeInTheDocument();
  });

  it("passes the typed note to onApprove and onReject", () => {
    const props = renderRow({ expanded: true });

    fireEvent.change(screen.getByLabelText("Review note"), {
      target: { value: "numbers checked" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(props.onApprove).toHaveBeenCalledWith("numbers checked");

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(props.onReject).toHaveBeenCalledWith("numbers checked");
  });

  it("hides the review controls once a run has been reviewed", () => {
    renderRow({
      run: { ...RUN, review_status: "approved", review_note: "checked" },
      expanded: true,
    });
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByText("checked")).toBeInTheDocument();
  });

  it("offers a Re-queue button for a running run and calls onRequeue", () => {
    const props = renderRow({ run: { ...RUN, status: "running" }, expanded: true });

    fireEvent.click(screen.getByRole("button", { name: "Re-queue" }));
    expect(props.onRequeue).toHaveBeenCalled();
  });

  it("does not offer a Re-queue button for a run that is not running", () => {
    renderRow({ run: { ...RUN, status: "done" }, expanded: true });
    expect(screen.queryByRole("button", { name: "Re-queue" })).not.toBeInTheDocument();
  });
});
