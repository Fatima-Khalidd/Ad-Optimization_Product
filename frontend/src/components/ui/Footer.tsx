import Link from "next/link";

const POLICY_LINKS = [
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
  { href: "/refunds", label: "Refunds" },
] as const;

export function Footer() {
  return (
    <footer className="mt-24 border-t border-slate/20 px-6 py-8">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 text-sm text-slate">
        <p>&copy; {new Date().getFullYear()} Ad Spend Optimization</p>
        <nav aria-label="Legal" className="flex flex-wrap gap-6">
          {POLICY_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="transition-colors hover:text-teal">
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
