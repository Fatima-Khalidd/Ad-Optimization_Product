import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import FlowStatic from "./FlowStatic";

describe("FlowStatic", () => {
  it("labels the budget, working spend and waste with real rupee figures", () => {
    render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    expect(screen.getByText("Rs. 400,000")).toBeInTheDocument();
    expect(screen.getByText("Rs. 100,000")).toBeInTheDocument();
    expect(screen.getByText("Rs. 300,000")).toBeInTheDocument();
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("Working spend")).toBeInTheDocument();
    expect(screen.getByText("Wasted")).toBeInTheDocument();
  });

  it("is an accessible image with the share spelled out", () => {
    render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Of Rs. 400,000 spent, Rs. 100,000 — 25.0% — is estimated waste.",
    );
  });

  it("scales the coral band thickness to the waste share", () => {
    render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    // BAND = 140 units; a 25% share means 35 coral against 105 teal.
    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "35");
    expect(screen.getByTestId("working-band")).toHaveAttribute("stroke-width", "105");
  });

  it("keeps a hairline coral band visible when almost nothing is wasted", () => {
    render(<FlowStatic headlineWaste={100} totalSpend={400000} />);

    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "3");
  });

  it("degrades to a zero-waste diagram when there is no spend", () => {
    render(<FlowStatic headlineWaste={0} totalSpend={0} />);

    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "3");
    expect(screen.getByTestId("working-band")).toHaveAttribute("stroke-width", "137");
    expect(screen.getAllByText("Rs. 0").length).toBeGreaterThan(0);
  });

  it("contains no animation at all — this is the reduced-motion fallback", () => {
    const { container } = render(<FlowStatic headlineWaste={100000} totalSpend={400000} />);

    expect(container.querySelector("animate")).toBeNull();
    expect(container.querySelector("animateTransform")).toBeNull();
    expect(container.innerHTML).not.toContain("animate-");
    expect(container.innerHTML).not.toContain("transition");
  });

  it("accepts the backend's decimal-string report shape (ReportOut)", () => {
    render(<FlowStatic headlineWaste="100000.00" totalSpend="400000.00" />);

    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "35");
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Of Rs. 400,000 spent, Rs. 100,000 — 25.0% — is estimated waste.",
    );
  });

  it("visibly differs in coral geometry between a 10% and a 50% waste share", () => {
    const { unmount } = render(<FlowStatic headlineWaste={10000} totalSpend={100000} />);
    const lowShareWidth = screen.getByTestId("waste-band").getAttribute("stroke-width");
    unmount();

    render(<FlowStatic headlineWaste={50000} totalSpend={100000} />);
    const highShareWidth = screen.getByTestId("waste-band").getAttribute("stroke-width");

    expect(lowShareWidth).toBe("14");
    expect(highShareWidth).toBe("70");
    expect(lowShareWidth).not.toBe(highShareWidth);
  });

  it("keeps 9-figure amounts inside the viewBox by right-anchoring the right-hand labels", () => {
    render(<FlowStatic headlineWaste="123456789.00" totalSpend="987654321.00" />);

    const workingLabel = screen.getByText("Working spend");
    const wastedLabel = screen.getByText("Wasted");
    const workingFigure = screen.getByText("Rs. 864,197,532");
    const wastedFigure = screen.getByText("Rs. 123,456,789");

    // viewBox is "0 0 800 420" — right-anchoring at x=780 (well inside 800) with
    // textAnchor="end" keeps text growing leftward from a fixed edge, so no width
    // of figure can run past the viewport regardless of digit count.
    [workingLabel, wastedLabel, workingFigure, wastedFigure].forEach((node) => {
      expect(node).toHaveAttribute("text-anchor", "end");
      expect(Number(node.getAttribute("x"))).toBeLessThanOrEqual(800);
    });
  });

  it("never renders a NaN attribute when given unparseable input", () => {
    const { container } = render(<FlowStatic headlineWaste="abc" totalSpend="abc" />);

    expect(container.innerHTML).not.toContain("NaN");
    expect(screen.getByTestId("waste-band")).toHaveAttribute("stroke-width", "3");
    expect(screen.getByTestId("working-band")).toHaveAttribute("stroke-width", "137");
  });
});
