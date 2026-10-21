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

  it("states the price in dollars, low on the page and without its own sales button", () => {
    const { container } = render(<Home />);

    expect(screen.getByRole("heading", { name: "What it costs" })).toBeInTheDocument();
    expect(screen.getByText(/\$65 a month, plus 20% of the ad waste you actually recover/)).toBeInTheDocument();
    expect(screen.queryByText(/Rs\. 15,000/)).not.toBeInTheDocument();
    // Comes after the method section, never ahead of what the product does.
    const ids = [...container.querySelectorAll("section[id]")].map((section) => section.id);
    expect(ids.indexOf("pricing")).toBeGreaterThan(ids.indexOf("method"));
    expect(container.querySelector("#pricing a")).toBeNull();
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
