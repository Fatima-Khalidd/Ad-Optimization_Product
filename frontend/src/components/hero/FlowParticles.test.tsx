import { describe, expect, it } from "vitest";

import { computeCoralShare } from "./FlowParticles";

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
