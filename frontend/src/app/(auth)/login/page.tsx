import Link from "next/link";

import AuthForm from "@/components/auth/AuthForm";

export const metadata = { title: "Log in · Ad Spend Optimization" };

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-10 px-6 py-16">
      <div className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-slate">Ad Spend Optimization</p>
        <h1 className="font-display text-4xl leading-tight">Welcome back.</h1>
      </div>
      <AuthForm mode="login" />
      <p className="text-sm text-slate">
        No account yet?{" "}
        <Link className="text-teal underline underline-offset-4" href="/signup">
          Create one
        </Link>
      </p>
    </main>
  );
}
