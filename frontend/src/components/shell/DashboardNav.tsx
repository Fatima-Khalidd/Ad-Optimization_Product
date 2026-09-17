"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import LogoutButton from "./LogoutButton";

const LINKS = [
  { href: "/dashboard", label: "Report" },
  { href: "/dashboard/upload", label: "Upload" },
  { href: "/dashboard/billing", label: "Billing" },
] as const;

export default function DashboardNav({ businessName }: { businessName: string }) {
  const pathname = usePathname();

  return (
    <header className="border-b border-slate/20">
      <nav className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-5 sm:px-6">
        <Link className="font-display text-base text-paper" href="/dashboard">
          {businessName}
        </Link>
        <div className="flex items-center gap-6 text-sm font-body">
          {LINKS.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "text-teal"
                    : "text-slate transition-colors hover:text-paper"
                }
                href={link.href}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
        <div className="ml-auto">
          <LogoutButton />
        </div>
      </nav>
    </header>
  );
}
