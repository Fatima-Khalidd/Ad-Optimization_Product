import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CountUp from "./CountUp";

describe("CountUp", () => {
  it("renders the final figure immediately when animation is off", () => {
    render(<CountUp animate={false} value={100000} />);

    expect(screen.getByText("Rs. 100,000")).toBeInTheDocument();
  });

  it("starts at zero and lands exactly on the value when animating", async () => {
    render(<CountUp animate durationMs={40} value={100000} />);

    expect(screen.getByText("Rs. 0")).toBeInTheDocument();
    expect(await screen.findByText("Rs. 100,000")).toBeInTheDocument();
  });

  it("never paints the final figure before dropping to zero (no hydration rewind flash)", () => {
    // The seed-to-`value`-then-drop-to-0 happens inside a useLayoutEffect, which React
    // flushes synchronously as part of the commit that `render()` triggers — so by the
    // time render() returns, the DOM must already show 0, never a fleeting "Rs. 100,000"
    // that a passive effect (running after paint) would have left visible for a frame.
    render(<CountUp animate durationMs={40} value={100000} />);

    expect(screen.queryByText("Rs. 100,000")).not.toBeInTheDocument();
    expect(screen.getByText("Rs. 0")).toBeInTheDocument();
  });

  it("uses a caller-supplied formatter", () => {
    render(<CountUp animate={false} format={(n) => `${n} leaks`} value={7} />);

    expect(screen.getByText("7 leaks")).toBeInTheDocument();
  });
});
