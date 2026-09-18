import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PrivacyPage from "@/app/privacy/page";
import RefundsPage from "@/app/refunds/page";
import TermsPage from "@/app/terms/page";

describe("policy pages", () => {
  it("renders the Terms page with a heading", () => {
    render(<TermsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Terms of Service" })).toBeInTheDocument();
  });

  it("renders the Privacy page with a heading", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Privacy Policy" })).toBeInTheDocument();
  });

  it("renders the Refunds page with a heading", () => {
    render(<RefundsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Refund Policy" })).toBeInTheDocument();
  });

  it("marks every unwritten clause with TODO-OWNER so none ships unnoticed", () => {
    for (const Page of [TermsPage, PrivacyPage, RefundsPage]) {
      const { container, unmount } = render(<Page />);
      expect(container.textContent).toContain("TODO-OWNER");
      unmount();
    }
  });

  it("names the manual payment methods on the refund page", () => {
    render(<RefundsPage />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("JazzCash");
    expect(text).toContain("Easypaisa");
    expect(text).toContain("Raast");
  });
});
