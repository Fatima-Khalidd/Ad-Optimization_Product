import { formatPKR, formatPct, wasteShare } from "@/lib/format";
import { HERO_COLORS } from "@/lib/motion";

/** Combined thickness of the two bands, in viewBox units. FlowParticles splits the same way. */
export const BAND = 140;

type Amount = string | number;

type Props = { totalSpend: Amount; headlineWaste: Amount };

/**
 * ReportOut delivers money as decimal STRINGS ("400000.00"), not numbers.
 * Geometry math needs a real number, and a finite one — an unparseable or
 * missing value must never reach an SVG attribute as NaN (React throws a
 * warning and silently drops the element). Anything that doesn't parse
 * collapses to 0, which — combined with wasteShare's own total<=0 guard —
 * degrades to the same "zero waste, full teal" diagram as no spend at all.
 */
function toFiniteNumber(value: Amount): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

/**
 * The static hero, and the prefers-reduced-motion fallback — so it has to tell
 * the whole story by itself: how much went in, how much worked, how much leaked.
 * Pure and deterministic (no hooks, no timers, no client-only APIs) so it
 * renders identically on the server and in tests, and Task 8 can swap it in
 * as the reduced-motion branch. Deliberately free of <animate>, CSS
 * transitions and hover effects — this component must contain no motion.
 */
export default function FlowStatic({ totalSpend, headlineWaste }: Props) {
  const total = toFiniteNumber(totalSpend);
  const waste = toFiniteNumber(headlineWaste);
  const share = wasteShare(waste, total);
  const coralWidth = Math.max(3, Math.round(BAND * share));
  const workingWidth = Math.max(3, BAND - coralWidth);
  const working = Math.max(0, total - waste);

  return (
    <svg
      aria-label={`Of ${formatPKR(total)} spent, ${formatPKR(waste)} — ${formatPct(
        share * 100,
      )} — is estimated waste.`}
      className="h-full w-full"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      viewBox="0 0 800 420"
    >
      <defs>
        <linearGradient id="flow-working" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor={HERO_COLORS.teal} stopOpacity="0.35" />
          <stop offset="100%" stopColor={HERO_COLORS.teal} stopOpacity="0.9" />
        </linearGradient>
        <linearGradient id="flow-waste" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor={HERO_COLORS.coral} stopOpacity="0.25" />
          <stop offset="100%" stopColor={HERO_COLORS.coral} stopOpacity="0.95" />
        </linearGradient>
      </defs>

      {/* Budget source */}
      <rect fill="url(#flow-working)" height={BAND} rx="4" width="14" x="96" y="110" />
      <text fill={HERO_COLORS.slate} fontSize="15" letterSpacing="2" x="40" y="88">
        Budget
      </text>
      <text className="numeral" fill="currentColor" fontSize="30" x="40" y="286">
        {formatPKR(total)}
      </text>

      {/* Working spend: straight through to the conversions node */}
      <path
        d="M 110 180 C 300 180, 420 150, 620 150"
        data-testid="working-band"
        fill="none"
        stroke="url(#flow-working)"
        strokeLinecap="butt"
        strokeWidth={workingWidth}
      />

      {/* Waste: peels downward */}
      <path
        d="M 110 240 C 300 250, 380 300, 620 348"
        data-testid="waste-band"
        fill="none"
        stroke="url(#flow-waste)"
        strokeLinecap="butt"
        strokeWidth={coralWidth}
      />

      {/* Working-spend node */}
      <circle cx="640" cy="150" fill={HERO_COLORS.teal} r="9" />
      <text fill={HERO_COLORS.slate} fontSize="15" letterSpacing="2" x="662" y="140">
        Working spend
      </text>
      <text className="numeral" fill="currentColor" fontSize="24" x="662" y="172">
        {formatPKR(working)}
      </text>

      {/* Wasted node */}
      <circle cx="640" cy="348" fill={HERO_COLORS.coral} r="9" />
      <text fill={HERO_COLORS.coral} fontSize="15" letterSpacing="2" x="662" y="338">
        Wasted
      </text>
      <text className="numeral" fill={HERO_COLORS.coral} fontSize="24" x="662" y="370">
        {formatPKR(waste)}
      </text>
    </svg>
  );
}
