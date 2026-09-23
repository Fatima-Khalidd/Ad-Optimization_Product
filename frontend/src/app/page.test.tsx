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

  it("routes every call to action to the contact block, not to self-serve sign-up", () => {
    const { container } = render(<Home />);

    const ctas = screen.getAllByRole("link", { name: /free audit/i });
    expect(ctas.length).toBeGreaterThan(0);
    for (const link of ctas) {
      expect(link).toHaveAttribute("href", "#contact");
    }
    expect(container.querySelector("#contact")).not.toBeNull();
    // A prospect must never be handed a form that cannot submit.
    expect(screen.queryByRole("link", { name: /create an account/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^get started$/i })).not.toBeInTheDocument();
  });

  it("offers WhatsApp, in the form wa.me actually accepts", () => {
    render(<Home />);

    // wa.me wants full international form, digits only — a leading 0 or a "+"
    // gives a "phone number shared via url is invalid" page, and the enquiry
    // is lost with no error anyone would notice.
    const wa = screen.getByRole("link", { name: /whatsapp/i });
    expect(wa.getAttribute("href")).toMatch(/^https:\/\/wa\.me\/92\d{10}\?/);
    expect(screen.getByText("0321 2964496")).toBeInTheDocument();
  });

  it("prints the address as readable text, not only as a mailto link", () => {
    render(<Home />);

    // A mailto: does nothing at all on a machine with no mail client
    // configured, so the address has to be selectable and copyable on the page.
    expect(screen.getByText("fatimakhalidddd0@gmail.com")).toBeInTheDocument();
  });
});
