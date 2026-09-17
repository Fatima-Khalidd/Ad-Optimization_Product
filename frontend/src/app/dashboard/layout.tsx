import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import DashboardNav from "@/components/shell/DashboardNav";
import { getMe } from "@/lib/server-api";

/**
 * The auth guard for /dashboard/*. It forwards the request cookies to
 * GET /api/auth/me and sends anyone without a valid session to /login.
 * Calling cookies() (inside getMe -> serverFetch) already opts this subtree
 * out of static rendering, but we also force it explicitly: a cached 200
 * here would let a logged-out visitor see another client's shell.
 */
export const dynamic = "force-dynamic";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const me = await getMe();
  if (me === null) {
    redirect("/login");
  }

  // /dashboard is the client-facing area; admins get their own area (Stage 6).
  if (me.user.role === "admin") {
    redirect("/admin");
  }

  return (
    <div className="min-h-screen">
      <DashboardNav businessName={me.client?.business_name ?? me.user.email} />
      <main className="mx-auto w-full max-w-6xl px-4 pb-24 pt-10 sm:px-6">{children}</main>
    </div>
  );
}
