import Link from "next/link";

const SECTIONS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#method", label: "Method" },
  { href: "#pricing", label: "Pricing" },
] as const;

/**
 * Landing-only header. It is deliberately not in the root layout: the
 * dashboard and admin screens have their own shell, and a marketing nav
 * bar on top of a working report would be noise.
 */
export default function LandingNav() {
  return (
    <header className="absolute inset-x-0 top-0 z-20">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-6 py-6">
        <Link className="font-display text-sm tracking-wide text-paper" href="/">
          Ad Spend Optimization
        </Link>

        <nav aria-label="Sections" className="hidden gap-8 text-sm text-slate md:flex">
          {SECTIONS.map((section) => (
            <Link
              className="transition-colors hover:text-paper"
              href={section.href}
              key={section.href}
            >
              {section.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-5 text-sm">
          <Link className="text-slate transition-colors hover:text-paper" href="/login">
            Sign in
          </Link>
          <Link
            className="rounded-sm border border-slate/40 px-4 py-2 text-paper transition-colors hover:border-slate"
            href="/signup"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}
