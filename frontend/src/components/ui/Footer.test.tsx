import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Footer } from "@/components/ui/Footer";

describe("Footer", () => {
  it("links to all three policy pages", () => {
    render(<Footer />);
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Refunds" })).toHaveAttribute("href", "/refunds");
  });

  it("labels the legal navigation for screen readers", () => {
    render(<Footer />);
    expect(screen.getByRole("navigation", { name: "Legal" })).toBeInTheDocument();
  });
});
