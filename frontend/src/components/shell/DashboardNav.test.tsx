import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DashboardNav from "./DashboardNav";

const usePathname = vi.fn();

// LogoutButton (rendered inside DashboardNav) calls useRouter, so both
// next/navigation hooks need a mock here.
vi.mock("next/navigation", () => ({
  usePathname: () => usePathname(),
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

describe("DashboardNav", () => {
  it("renders exactly the Report and Upload links, with no link to /dashboard/billing", () => {
    usePathname.mockReturnValue("/dashboard");
    render(<DashboardNav businessName="Acme" />);

    const links = screen.getAllByRole("link").filter((link) => link.textContent !== "Acme");
    expect(links.map((link) => link.textContent)).toEqual(["Report", "Upload"]);
    expect(screen.queryByRole("link", { name: "Billing" })).not.toBeInTheDocument();
    links.forEach((link) => expect(link).not.toHaveAttribute("href", "/dashboard/billing"));
  });

  it("marks the active link with aria-current='page'", () => {
    usePathname.mockReturnValue("/dashboard/upload");
    render(<DashboardNav businessName="Acme" />);

    expect(screen.getByRole("link", { name: "Upload" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Report" })).not.toHaveAttribute("aria-current");
  });
});
