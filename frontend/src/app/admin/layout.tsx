import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { getMe } from "@/lib/server-api";

const NAV = [
  { href: "/admin/runs", label: "Runs" },
  { href: "/admin/clients", label: "Clients" },
  { href: "/admin/invoices", label: "Invoices" },
  { href: "/admin/payments", label: "Payments" },
  { href: "/admin/payment-methods", label: "Payment accounts" },
  { href: "/admin/audit", label: "Audit log" },
];

/**
 * The auth guard for /admin/*, mirroring dashboard/layout.tsx: forward the
 * request cookies to GET /api/auth/me via serverFetch (never apiFetch — this
 * is a server component and apiFetch's relative URLs throw here), send
 * anyone without a valid session to /login, and send a non-admin to
 * /dashboard. /dashboard/layout.tsx redirects an admin to /admin, so the two
 * guards are complementary, not circular: an admin never bounces back here
 * from /dashboard, and a client never bounces back to /dashboard from here.
 */
export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const me = await getMe();
  if (me === null) {
    redirect("/login");
  }
  if (me.user.role !== "admin") {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen">
      <header className="flex items-baseline gap-6 border-b border-white/15 px-6 py-3">
        <span className="font-display text-base">Admin</span>
        <nav className="flex gap-4 text-sm text-slate">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-paper">
              {item.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto text-xs text-slate">{me.user.email}</span>
      </header>
      <main className="px-6 py-5">{children}</main>
    </div>
  );
}
