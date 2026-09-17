"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { ApiError, apiFetch } from "@/lib/api";
import type { MeOut } from "@/lib/types";

type Props = { mode: "login" | "signup" };

export default function AuthForm({ mode }: Props) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isSignup = mode === "signup";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);

    const data = new FormData(event.currentTarget);
    const payload: Record<string, string> = {
      email: String(data.get("email") ?? ""),
      password: String(data.get("password") ?? ""),
    };
    if (isSignup) {
      payload.business_name = String(data.get("business_name") ?? "");
    }

    try {
      await apiFetch<MeOut>(`/api/auth/${mode}`, { method: "POST", body: JSON.stringify(payload) });
      router.push("/dashboard");
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(
          caught.status === 429
            ? "Too many attempts. Wait a minute and try again."
            : formatApiErrorMessage(caught),
        );
      } else {
        setError("Could not reach the server. Check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="flex flex-col gap-6" onSubmit={onSubmit} noValidate>
      {isSignup ? <Field label="Business name" name="business_name" autoComplete="organization" /> : null}
      <Field label="Email" name="email" type="email" autoComplete="email" />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete={isSignup ? "new-password" : "current-password"}
        minLength={isSignup ? 8 : undefined}
      />
      {error ? (
        <p className="text-sm text-coral" role="alert">
          {error}
        </p>
      ) : null}
      <Button disabled={busy} type="submit">
        {busy ? "Please wait…" : isSignup ? "Create account" : "Log in"}
      </Button>
    </form>
  );
}

const FIELD_LABELS: Record<string, string> = {
  email: "Email",
  password: "Password",
  business_name: "Business name",
};

/**
 * FastAPI's 422 `detail` is a list of `{loc, msg, type}` for pydantic validation
 * errors; `loc` is e.g. ["body", "password"]. Map the last segment to a human field
 * name and join into readable sentences. Any other detail shape (401/409/429/500)
 * is already a plain string by the time apiFetch/ApiError hands it to us via `.message`.
 */
function formatApiErrorMessage(error: ApiError): string {
  const { detail } = error;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (item !== null && typeof item === "object" && "msg" in item) {
        const entry = item as { loc?: unknown; msg?: unknown };
        const loc = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : undefined;
        const field = typeof loc === "string" ? (FIELD_LABELS[loc] ?? loc) : null;
        const msg = typeof entry.msg === "string" ? entry.msg : "Invalid value";
        return field ? `${field}: ${msg}` : msg;
      }
      return "Invalid value";
    });
    return messages.join(" ");
  }
  return error.message;
}
