"use client";

import dynamic from "next/dynamic";

import FlowStatic from "@/components/hero/FlowStatic";
import { useReducedMotion } from "@/lib/motion";

// Three.js is large. Behind dynamic(ssr:false) the tables and numbers never
// wait for it, and it never runs on the server. ssr:false is legal here only
// because this file is itself a client component.
const FlowParticles = dynamic(() => import("@/components/hero/FlowParticles"), {
  ssr: false,
  loading: () => null,
});

type Amount = string | number;

type Props = { totalSpend: Amount; headlineWaste: Amount };

/**
 * The switch: reduced motion (or the server, before hydration) always gets
 * the pure, deterministic FlowStatic; everyone else gets the one-shot
 * particle stream. The accessible role="img"/aria-label lives inside each
 * branch's own component (FlowStatic for Task 7, FlowParticles here) so a
 * screen-reader visitor gets the identical numbers from either branch.
 */
export default function Hero({ totalSpend, headlineWaste }: Props) {
  const reduced = useReducedMotion();

  if (reduced) {
    return <FlowStatic headlineWaste={headlineWaste} totalSpend={totalSpend} />;
  }
  return <FlowParticles headlineWaste={headlineWaste} totalSpend={totalSpend} />;
}
