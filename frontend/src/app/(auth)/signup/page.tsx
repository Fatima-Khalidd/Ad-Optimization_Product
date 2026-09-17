import Link from "next/link";

import AuthForm from "@/components/auth/AuthForm";

export const metadata = { title: "Sign up · Ad Spend Optimization" };

export default function SignupPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-10 px-6 py-16">
      <div className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-slate">Ad Spend Optimization</p>
        <h1 className="font-display text-4xl leading-tight">Find the leak in your ad spend.</h1>
        <p className="text-slate">Upload one export. We tell you which segments are burning money.</p>
      </div>
      <AuthForm mode="signup" />
      <p className="text-sm text-slate">
        Already have an account?{" "}
        <Link className="text-teal underline underline-offset-4" href="/login">
          Log in
        </Link>
      </p>
    </main>
  );
}
