import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Home from "./page";

// The hero is covered by CinematicHero.test.tsx; jsdom has no media playback,
// so this test stubs it out and stays on the marketing content.
vi.mock("@/components/landing/CinematicHero", () => ({
  default: () => <div data-testid="hero" />,
}));

describe("landing page", () => {
  it("renders every section the nav links to", () => {
    const { container } = render(<Home />);

    // A nav link pointing at an id that does not exist is a dead link that no
    // type checker catches, so assert the anchors resolve.
    for (const id of ["how-it-works", "method", "pricing"]) {
      expect(container.querySelector(`#${id}`)).not.toBeNull();
    }
  });

  it("states the pricing model without inventing a figure", () => {
    render(<Home />);

    expect(screen.getByText(/share of what you save/i)).toBeInTheDocument();
    expect(screen.getByText(/only on waste you actually recover/i)).toBeInTheDocument();
  });

  it("does not claim the analysis is AI", () => {
    render(<Home />);

    // The engine is arithmetic against the account's own average. Claiming a
    // model would be a straightforward lie to a prospect, and the FAQ says so.
    expect(screen.getByText(/^Is this AI\?$/)).toBeInTheDocument();
    expect(screen.getByText(/No\. It is arithmetic/)).toBeInTheDocument();
  });

  it("names the payment methods a Pakistani business actually uses", () => {
    render(<Home />);

    expect(screen.getAllByText(/JazzCash, Easypaisa/).length).toBeGreaterThan(0);
  });

  it("offers a way in", () => {
    render(<Home />);

    const signups = screen.getAllByRole("link", { name: /create an account/i });
    expect(signups.length).toBeGreaterThan(0);
    for (const link of signups) {
      expect(link).toHaveAttribute("href", "/signup");
    }
  });
});
