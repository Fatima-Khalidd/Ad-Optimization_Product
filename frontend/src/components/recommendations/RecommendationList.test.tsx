import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import RecommendationList from "./RecommendationList";
import type { RecommendationOut } from "@/lib/types";

// Money fields (current_spend, recommended_cut) are decimal STRINGS on the
// wire (INTERFACES.md "Stage 3 close-out" #2), never plain numbers.
const recommendations: RecommendationOut[] = [
  {
    id: 1,
    dimension: "placement",
    segment_name: "audience_network",
    current_spend: "84000",
    recommended_cut: "50400",
    reason:
      "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — 2.6x your placement average of Rs. 800. Cut Rs. 50,400 (60%).",
  },
  {
    id: 2,
    dimension: "age_group",
    segment_name: "55-64",
    current_spend: "20000",
    recommended_cut: "12000",
    reason:
      "55-64 spent Rs. 20,000 at Rs. 4,000 per conversion — 5.0x your age group average of Rs. 800. Cut Rs. 12,000 (60%).",
  },
];

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

describe("RecommendationList", () => {
  it("lists every recommendation collapsed, showing the cut and the dimension", () => {
    setReducedMotion(false);
    render(<RecommendationList recommendations={recommendations} />);

    const trigger = screen.getByRole("button", { name: /Audience Network/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    // aria-controls must not reference a panel id that does not exist in the
    // DOM — the panel is unmounted while collapsed, so the attribute is
    // dropped entirely rather than pointing at nothing.
    expect(trigger).not.toHaveAttribute("aria-controls");
    expect(screen.getByText("Cut Rs. 50,400")).toBeInTheDocument();
    expect(screen.getByText("Placement")).toBeInTheDocument();
    expect(screen.queryByText(recommendations[0].reason)).not.toBeInTheDocument();
  });

  it("reveals the reason when the row is clicked", async () => {
    setReducedMotion(false);
    const user = userEvent.setup();
    render(<RecommendationList recommendations={recommendations} />);

    await user.click(screen.getByRole("button", { name: /Audience Network/ }));

    expect(await screen.findByText(recommendations[0].reason)).toBeInTheDocument();
    const trigger = screen.getByRole("button", { name: /Audience Network/ });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Currently spending Rs. 84,000")).toBeInTheDocument();
    // Once expanded, aria-controls names the now-existing panel element.
    const controlsId = trigger.getAttribute("aria-controls");
    expect(controlsId).toBeTruthy();
    expect(document.getElementById(controlsId as string)).toBeInTheDocument();
  });

  it("collapses again on a second click", async () => {
    setReducedMotion(false);
    const user = userEvent.setup();
    render(<RecommendationList recommendations={recommendations} />);
    const trigger = screen.getByRole("button", { name: /Audience Network/ });

    await user.click(trigger);
    await screen.findByText(recommendations[0].reason);
    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await waitFor(
      () => expect(screen.queryByText(recommendations[0].reason)).not.toBeInTheDocument(),
      { timeout: 3000 },
    );
  });

  it("keeps only one item open at a time", async () => {
    setReducedMotion(false);
    const user = userEvent.setup();
    render(<RecommendationList recommendations={recommendations} />);

    await user.click(screen.getByRole("button", { name: /Audience Network/ }));
    await user.click(screen.getByRole("button", { name: /55-64/ }));

    expect(screen.getByRole("button", { name: /55-64/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /Audience Network/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("says so plainly when nothing needs cutting", () => {
    setReducedMotion(false);
    render(<RecommendationList recommendations={[]} />);

    expect(screen.getByText(/No segment is spending above the benchmark/i)).toBeInTheDocument();
  });

  it("renders the reason immediately, without animating, when reduced motion is set", async () => {
    setReducedMotion(true);
    const user = userEvent.setup();
    render(<RecommendationList recommendations={recommendations} />);

    await user.click(screen.getByRole("button", { name: /Audience Network/ }));

    // No findBy/waitFor: reduced motion means the content is already there on
    // the click's own render, with no animation frame to wait out.
    expect(screen.getByText(recommendations[0].reason)).toBeInTheDocument();
  });
});
