export default function Home() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-24">
      <p className="text-sm uppercase tracking-widest text-slate">Ad Spend Optimization</p>
      <h1 className="font-display text-5xl">Find the money leaking out of your ads.</h1>
      <p className="max-w-xl text-slate">
        Scaffold only — the dashboard arrives in Stage 4. Backend health:{" "}
        <a className="text-teal underline" href="/api/health">
          /api/health
        </a>
      </p>
    </main>
  );
}
