"use client";

import { useSyncExternalStore } from "react";

export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/** The single bold animation runs for exactly this long, once. The count-up is synced to it. */
export const HERO_DURATION_MS = 4000;

/**
 * The only place hex literals are allowed outside globals.css: SVG gradient
 * stops and Three.js colour buffers cannot read Tailwind utilities.
 * These MUST stay identical to the --color-* tokens in globals.css.
 */
export const HERO_COLORS = {
  teal: "#2dd4bf",
  coral: "#ff6b4a",
  slate: "#8891a5",
} as const;

function subscribe(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/** The server has no media queries, so it always renders the reduced-motion (static) hero. */
function getServerSnapshot(): boolean {
  return true;
}

/**
 * True until the browser says otherwise, so the server render and the first
 * paint are always the static hero — someone who asked for no motion never
 * catches a frame of it. Built on useSyncExternalStore (not a state+effect
 * pair) so the media-query value is read directly rather than pushed
 * through a synchronous setState-in-effect, which react-hooks/set-state-in-effect
 * flags as a cascading-render risk.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
