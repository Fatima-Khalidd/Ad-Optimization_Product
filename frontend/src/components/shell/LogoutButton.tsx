"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiFetch } from "@/lib/api";

export default function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    try {
      await apiFetch<void>("/api/auth/logout", { method: "POST" });
    } catch {
      // The cookie may already be gone. Leave anyway — the guard will sort it out.
    }
    router.push("/login");
    router.refresh();
  }

  return (
    <button
      className="text-sm text-slate transition-colors hover:text-paper disabled:opacity-50"
      disabled={busy}
      onClick={logout}
      type="button"
    >
      Log out
    </button>
  );
}
