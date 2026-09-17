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

  it("uses a caller-supplied formatter", () => {
    render(<CountUp animate={false} format={(n) => `${n} leaks`} value={7} />);

    expect(screen.getByText("7 leaks")).toBeInTheDocument();
  });
});
