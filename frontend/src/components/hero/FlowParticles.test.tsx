import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// jsdom has no WebGL, so Canvas is replaced with a plain stub that renders a
// bare <canvas> and ignores its children — this proves FlowParticles' own
// wrapper markup (role="img", aria-label, aria-hidden canvas) without ever
// needing the Stream/points/PointMaterial tree to actually mount.
vi.mock("@react-three/fiber", () => ({
  Canvas: (props: { "aria-hidden"?: boolean | "true" | "false" }) => (
    <canvas aria-hidden={props["aria-hidden"]} data-testid="canvas-stub" />
  ),
  useFrame: () => {},
}));

vi.mock("@react-three/drei", () => ({
  PointMaterial: () => null,
}));

import { computeCoralShare } from "./FlowParticles";
import FlowParticles from "./FlowParticles";

// FlowParticles itself is never rendered in tests (jsdom has no WebGL — see
// Hero.test.tsx, which mocks the whole module). What CAN be verified without
// a GPU is the pure math that decides the coral/teal split: computeCoralShare
// is the exact function FlowParticles calls to size the wasteful lane, so
// asserting on it directly proves the split is honest about the real number,
// without needing a canvas.
describe("computeCoralShare", () => {
  it("equals the waste share for numeric props", () => {
    expect(computeCoralShare({ headlineWaste: 100000, totalSpend: 400000 })).toBeCloseTo(0.25);
  });

  it("parses the backend's decimal-string money fields", () => {
    expect(
      computeCoralShare({ headlineWaste: "84000.00", totalSpend: "420000.00" }),
    ).toBeCloseTo(0.2);
  });

  it("clamps to [0, 1]", () => {
    expect(computeCoralShare({ headlineWaste: 500000, totalSpend: 100000 })).toBe(1);
    expect(computeCoralShare({ headlineWaste: -100, totalSpend: 100000 })).toBe(0);
  });

  it("degrades to 0 on unparseable or missing input", () => {
    expect(computeCoralShare({ headlineWaste: "not-a-number", totalSpend: 400000 })).toBe(0);
    expect(computeCoralShare({ headlineWaste: 100000, totalSpend: "" })).toBe(0);
  });
});

describe("FlowParticles accessibility", () => {
  it("exposes role=img with a numeric aria-label, and hides the canvas from assistive tech", () => {
    render(<FlowParticles headlineWaste={100000} totalSpend={400000} />);

    const image = screen.getByRole("img");
    expect(image).toHaveAccessibleName("Of Rs. 400,000 spent, Rs. 100,000 — 25.0% — is estimated waste.");

    const canvas = screen.getByTestId("canvas-stub");
    expect(canvas).toHaveAttribute("aria-hidden", "true");
  });
});
