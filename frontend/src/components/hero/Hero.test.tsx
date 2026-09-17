import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Hero from "./Hero";

// jsdom cannot run WebGL. The particle stream is replaced by a marker so this
// test only exercises Hero's reduced-motion branch.
vi.mock("@/components/hero/FlowParticles", () => ({
  default: ({ headlineWaste }: { headlineWaste: number }) => (
    <div data-testid="flow-particles">{headlineWaste}</div>
  ),
}));

function setReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("Hero", () => {
  it("renders the static SVG when the visitor asked for reduced motion", async () => {
    setReducedMotion(true);

    render(<Hero headlineWaste={100000} totalSpend={400000} />);

    expect(await screen.findByRole("img")).toHaveAccessibleName(/Rs. 100,000/);
    // The mocked particle component carries no role="img" of its own, so its
    // absence here only proves the mock never mounted on this branch — it says
    // nothing about the real FlowParticles' accessibility, which is covered
    // separately by FlowParticles.test.tsx.
    expect(screen.queryByTestId("flow-particles")).not.toBeInTheDocument();
  });

  it("asks the browser with the prefers-reduced-motion query", () => {
    setReducedMotion(true);

    render(<Hero headlineWaste={100000} totalSpend={400000} />);

    expect(window.matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");
  });

  it("swaps in the particle stream when motion is allowed", async () => {
    setReducedMotion(false);

    render(<Hero headlineWaste={100000} totalSpend={400000} />);

    // Asserts the mocked particle component was rendered on this branch — not that
    // role="img" is absent (the mock has no accessibility markup of its own, so that
    // assertion would be true regardless of what the real FlowParticles renders, and
    // is misleading about real behaviour; FlowParticles.test.tsx verifies role="img"
    // against the real component with only its Canvas stubbed).
    expect(await screen.findByTestId("flow-particles")).toHaveTextContent("100000");
  });
});
