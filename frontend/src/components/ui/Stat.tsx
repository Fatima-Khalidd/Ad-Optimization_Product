import type { ReactNode } from "react";

/**
 * A key number as large type — deliberately NOT a card: no border, no
 * background, no shadow (docs/PLAN.md §6 Stage 4).
 */
export default function Stat({
  label,
  accent = false,
  testId,
  children,
}: {
  label: string;
  accent?: boolean;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-slate">{label}</p>
      <p
        className={`mt-2 font-display text-4xl leading-none tabular-nums sm:text-5xl lg:text-6xl ${
          accent ? "text-coral" : "text-paper"
        }`}
        data-testid={testId}
      >
        {children}
      </p>
    </div>
  );
}
