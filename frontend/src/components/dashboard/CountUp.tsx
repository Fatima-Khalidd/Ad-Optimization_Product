"use client";

import { useEffect, useState } from "react";

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
  // Only ever read when animate is true (see `displayed` below), so its
  // initial value never leaks into the animate={false} render path.
  const [shown, setShown] = useState(0);

  useEffect(() => {
    // No setState here: when animation is off there is nothing to
    // synchronize with an external system, and `displayed` below already
    // renders `value` directly. (A synchronous setState in an effect body
    // is what react-hooks/set-state-in-effect flags as cascading-render
    // risk — the setShown calls below happen inside the rAF callback, an
    // external-system subscription, which the rule allows.)
    if (!animate) return;

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
