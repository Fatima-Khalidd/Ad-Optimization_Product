"use client";

import CountUp from "@/components/dashboard/CountUp";
import Stat from "@/components/ui/Stat";
import { formatPKR, formatPct } from "@/lib/format";
import { useReducedMotion } from "@/lib/motion";

type Amount = string | number;

type Props = {
  totalSpend: Amount;
  headlineWaste: Amount;
  recoveryPct: Amount;
  animate: boolean;
};

/**
 * The right-hand column. Only the waste figure counts up, and only when the
 * hero is animating too — so the number and the coral drip land together.
 *
 * total_spend/headline_waste/recovery_pct arrive from the backend as decimal
 * STRINGS (INTERFACES.md "Stage 3 close-out"), so formatPKR/formatPct take
 * them as-is; CountUp needs a plain number, so headlineWaste is parsed once
 * here rather than asking CountUp to understand the wire format.
 */
export default function SummaryNumbers({ totalSpend, headlineWaste, recoveryPct, animate }: Props) {
  const reduced = useReducedMotion();
  const counting = animate && !reduced;
  const headlineWasteNumber = Number(headlineWaste);

  return (
    <div className="flex flex-col justify-center gap-10">
      <Stat label="Total spend analysed" testId="stat-total-spend">
        {formatPKR(totalSpend)}
      </Stat>
      <Stat accent label="Estimated waste" testId="stat-headline-waste">
        <CountUp animate={counting} value={Number.isFinite(headlineWasteNumber) ? headlineWasteNumber : 0} />
      </Stat>
      <Stat label="Recoverable share of spend" testId="stat-recovery-pct">
        {formatPct(recoveryPct)}
      </Stat>
    </div>
  );
}
