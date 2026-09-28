import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Home from "./page";

vi.mock("@/components/landing/CinematicHero", () => ({
  default: () => <div data-testid="hero" />,
}));

describe("landing page", () => {
  it("renders every section the nav links to", () => {
    const { container } = render(<Home />);

    for (const id of ["how-it-works", "method", "pricing"]) {
      expect(container.querySelector(`#${id}`)).not.toBeNull();
    }
  });

  it("leaves pricing and access terms to the purchase offer", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "Plans and access" })).toBeInTheDocument();
    expect(
      screen.getByText(/pricing, access duration, and any usage limits are defined by the offer/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Rs\. 15,000/)).not.toBeInTheDocument();
    expect(screen.queryByText(/20%/)).not.toBeInTheDocument();
  });

  it("does not claim the analysis is AI", () => {
    render(<Home />);

    expect(screen.getByText(/^Is this AI\?$/)).toBeInTheDocument();
    expect(screen.getByText(/No\. It is arithmetic/)).toBeInTheDocument();
  });

  it("routes calls to action to self-serve account creation", () => {
    render(<Home />);

    const ctas = screen.getAllByRole("link", { name: /create account/i });
    expect(ctas.length).toBeGreaterThanOrEqual(1);
    for (const link of ctas) {
      expect(link).toHaveAttribute("href", "/signup");
    }
  });
});
