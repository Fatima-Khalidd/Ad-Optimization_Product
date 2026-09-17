import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6 py-24">
      <p className="text-sm uppercase tracking-widest text-slate">Ad Spend Optimization</p>
      <h1 className="font-display text-5xl leading-tight sm:text-6xl">
        Find the money leaking out of your ads.
      </h1>
      <p className="max-w-xl font-body text-slate">
        Upload one export. We compare every placement, age group and time slot against your own
        account average and show you, in rupees, exactly where the waste is.
      </p>
      <p className="max-w-xl font-body text-slate">
        Pricing is a small base fee plus a share of the waste you actually recover — you only pay
        the performance portion once an admin confirms the improvement.
      </p>
      <div className="mt-4 flex flex-wrap gap-6 text-sm">
        <Link className="text-teal underline underline-offset-4" href="/signup">
          Create an account
        </Link>
        <Link className="text-slate underline underline-offset-4 transition-colors hover:text-paper" href="/login">
          Sign in
        </Link>
      </div>
    </main>
  );
}
