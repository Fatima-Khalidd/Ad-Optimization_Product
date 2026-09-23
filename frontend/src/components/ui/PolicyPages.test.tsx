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

  // Was the inverse until the owner wrote the copy: the pages are now live text a
  // prospect reads before deciding whether to hand over their data, so a leftover
  // placeholder is worse than a missing clause.
  it("ships no placeholder text on any policy page", () => {
    for (const Page of [TermsPage, PrivacyPage, RefundsPage]) {
      const { container, unmount } = render(<Page />);
      expect(container.textContent).not.toContain("TODO");
      unmount();
    }
  });

  it("gives a contact address on every policy page", () => {
    for (const Page of [TermsPage, PrivacyPage, RefundsPage]) {
      const { container, unmount } = render(<Page />);
      expect(container.querySelector('a[href^="mailto:"]')).not.toBeNull();
      unmount();
    }
  });

  it("states the two fee rules the product enforces in code", () => {
    render(<TermsPage />);
    const text = document.body.textContent ?? "";
    // services/billing.py never charges a performance fee without an admin
    // confirming the recovery first; the terms must not promise otherwise.
    expect(text).toContain("confirmed with you first");
    expect(text).toContain("no performance fee");
  });

  it("names the manual payment methods on the refund page", () => {
    render(<RefundsPage />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("JazzCash");
    expect(text).toContain("Easypaisa");
    expect(text).toContain("Raast");
  });
});
