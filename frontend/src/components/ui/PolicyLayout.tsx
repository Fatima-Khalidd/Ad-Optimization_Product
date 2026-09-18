import type { ReactNode } from "react";

export function PolicyLayout({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-display text-4xl text-paper">{title}</h1>
      <p className="mt-2 text-sm text-slate">Last updated: {updated}</p>
      <div className="mt-10 space-y-8 text-paper/80 [&_h2]:font-display [&_h2]:text-xl [&_h2]:text-paper [&_p]:mt-2 [&_p]:leading-relaxed">
        {children}
      </div>
    </main>
  );
}
