"use client";

import { useLayoutEffect, useState } from "react";

import { formatPKR } from "@/lib/format";
import { HERO_DURATION_MS } from "@/lib/motion";

type Props = {
  value: number;
  animate: boolean;
  durationMs?: number;
  format?: (n: number) => string;
};

/**
 * Counts up over the same window as the hero's coral drip, so the number and
 * the picture land together. `animate={false}` — reduced motion, or an admin
 * view — renders the final figure with no movement at all.
 */
export default function CountUp({
  value,
  animate,
  durationMs = HERO_DURATION_MS,
  format = formatPKR,
}: Props) {
  // Seeded to `value`, not 0: the server always renders the final figure
  // (reduced motion on the server — see useReducedMotion's getServerSnapshot),
  // so an animate={true} first client render must start from that same final
  // text or hydration mismatches and the wrong number is briefly visible.
  const [shown, setShown] = useState(value);

  // A LAYOUT effect, not a passive one: it runs synchronously after the DOM
  // is updated but before the browser paints, so the reset to 0 below is
  // never itself painted as a separate frame — the browser's first
  // post-hydration paint already shows 0, not a "final value, then rewind
  // to 0" flash. This is the textbook use case useLayoutEffect exists for
  // (React docs: "measure layout... before the browser has a chance to
  // repaint"); react-hooks/set-state-in-effect's cascading-render warning is
  // aimed at useEffect cargo-culting external derived state, not at this.
  useLayoutEffect(() => {
    // No setState here when animation is off: `displayed` below already reads
    // `value` directly in that branch, so `shown` staying stale is harmless.
    if (!animate) return;

    // Deliberate pre-paint reset (see comment above); this is exactly what
    // useLayoutEffect is for, and it is what stops the SSR final value from
    // ever being visibly painted before the count-up begins.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setShown(0);

    let frame = 0;
    // Captured from the first rAF callback's own timestamp, not
    // performance.now(): jsdom's requestAnimationFrame runs on a clock that
    // is not synced with performance.now() (they can differ by seconds), so
    // seeding `start` from performance.now() produces a bogus elapsed time
    // and CountUp never lands on the target. Using the rAF clock for both
    // ends keeps this correct in the browser too.
    let start: number | null = null;

    const tick = (now: number) => {
      if (start === null) start = now;
      const progress = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic: quick, then settles
      setShown(value * eased); // eased === 1 on the last frame, so it lands exactly
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [animate, value, durationMs]);

  const displayed = animate ? shown : value;
  return <span>{format(displayed)}</span>;
}
