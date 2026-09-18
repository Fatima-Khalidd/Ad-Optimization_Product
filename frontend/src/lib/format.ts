/**
 * Every rupee figure in the UI goes through formatPKR, and every percentage
 * through formatPct. Components must never format money themselves.
 *
 * Both helpers accept the backend's native shape (a decimal STRING, e.g.
 * "84000.00" for money or "16.28" for recovery_pct — see
 * docs/superpowers/plans/INTERFACES.md "Stage 3 close-out") as well as a
 * plain `number`, so call sites never need to `Number()` a field first.
 *
 * Rule for missing/bad input: `null`/`undefined`/an unparseable STRING
 * render as an em dash ("—") — that is "no value yet", distinct from zero.
 * A non-finite NUMBER (NaN/Infinity) — which only happens from a caller's
 * own arithmetic, never from parsing backend JSON — still renders as the
 * zero value ("Rs. 0" / "0.0%"), matching the brief's original contract.
 */

type Amount = number | string | null | undefined;

const DASH = "—";

/** Whole rupees with thousands separators: formatPKR(84000) -> "Rs. 84,000"; formatPKR("84000.00") -> same. */
export function formatPKR(n: Amount): string {
  if (n === null || n === undefined) return DASH;
  if (typeof n === "string") {
    if (n.trim().length === 0) return DASH;
    const parsed = Number(n);
    if (!Number.isFinite(parsed)) return DASH;
    return formatPKR(parsed);
  }
  if (!Number.isFinite(n)) return "Rs. 0";
  const rounded = Math.round(n); // round-half-up for display; negatives round toward +Infinity at .5, matching Math.round
  const sign = rounded < 0 ? "-" : "";
  return `${sign}Rs. ${Math.abs(rounded).toLocaleString("en-US")}`;
}

/**
 * Exact rupees and paisa, two decimal places, with thousands separators:
 * formatPKRExact(4600.5) -> "Rs. 4,600.50"; formatPKRExact("4600.50") -> same.
 *
 * Same parsing and "—" rules as formatPKR, but never rounds — for the invoices screen,
 * where an admin has to defend the arithmetic (base fee + performance fee = total) to a
 * client, and independently-rounded whole-rupee figures can visibly fail to add up.
 */
export function formatPKRExact(n: Amount): string {
  if (n === null || n === undefined) return DASH;
  if (typeof n === "string") {
    if (n.trim().length === 0) return DASH;
    const parsed = Number(n);
    if (!Number.isFinite(parsed)) return DASH;
    return formatPKRExact(parsed);
  }
  if (!Number.isFinite(n)) return "Rs. 0.00";
  const sign = n < 0 ? "-" : "";
  const [whole, fraction] = Math.abs(n).toFixed(2).split(".");
  return `${sign}Rs. ${Number(whole).toLocaleString("en-US")}.${fraction}`;
}

/**
 * One decimal place. The input is already a percentage, not a fraction —
 * ReportOut.recovery_pct is headline_waste / total_spend * 100, delivered
 * as a decimal string (e.g. "16.28" -> "16.3%").
 */
export function formatPct(n: Amount): string {
  if (n === null || n === undefined) return DASH;
  if (typeof n === "string") {
    if (n.trim().length === 0) return DASH;
    const parsed = Number(n);
    if (!Number.isFinite(parsed)) return DASH;
    return formatPct(parsed);
  }
  if (!Number.isFinite(n)) return "0.0%";
  return `${n.toFixed(1)}%`;
}

/** "audience_network" -> "Audience Network"; "18-24" is left as it is. */
export function humanizeSegment(value: string): string {
  return value
    .split("_")
    .map((word) => (word.length > 0 ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
}

/** The 0..1 fraction of spend that is wasted. Drives the hero's teal/coral split. */
export function wasteShare(headlineWaste: number, totalSpend: number): number {
  if (!Number.isFinite(headlineWaste) || !Number.isFinite(totalSpend) || totalSpend <= 0) {
    return 0;
  }
  return Math.min(1, Math.max(0, headlineWaste / totalSpend));
}
