"use client";

import { PointMaterial } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { formatPKR, formatPct, wasteShare } from "@/lib/format";
import { HERO_COLORS, HERO_DURATION_MS } from "@/lib/motion";

const COUNT = 1400;
const DURATION = HERO_DURATION_MS / 1000;
const SPLIT = 0.52; // progress at which the wasteful particles start peeling away
const X_START = -4.4;
const X_END = 4.4;

type Amount = string | number;

type Props = { totalSpend: Amount; headlineWaste: Amount };

type Lanes = {
  phase: Float32Array; // 0..0.4 head start, so the stream has a leading edge
  laneY: Float32Array;
  drift: Float32Array;
  depth: Float32Array; // z-jitter, generated here (not inline in the geometry
  // useMemo below) so the only Math.random() calls in the module live in
  // this one non-hook function — react-hooks/purity flags an impure call
  // written directly inside a hook body, since that body runs during render.
  waste: Uint8Array;
};

/**
 * ReportOut delivers money as decimal STRINGS ("400000.00"), not numbers.
 * Mirrors FlowStatic's own toFiniteNumber so both components agree on the
 * same waste share for the same report — an unparseable/missing value
 * collapses to 0, matching FlowStatic's degrade-to-"no waste" behaviour.
 */
function toFiniteNumber(value: Amount): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

/** The real, honest fraction of spend that is wasted — drives the coral/teal particle split. */
export function computeCoralShare({ totalSpend, headlineWaste }: Props): number {
  return wasteShare(toFiniteNumber(headlineWaste), toFiniteNumber(totalSpend));
}

function makeLanes(share: number): Lanes {
  const phase = new Float32Array(COUNT);
  const laneY = new Float32Array(COUNT);
  const drift = new Float32Array(COUNT);
  const depth = new Float32Array(COUNT);
  const waste = new Uint8Array(COUNT);
  const wasteCount = Math.round(COUNT * share);

  for (let i = 0; i < COUNT; i += 1) {
    phase[i] = (i / COUNT) * 0.4;
    // The wasteful share rides the bottom of the band, so the peel reads cleanly.
    waste[i] = i < wasteCount ? 1 : 0;
    laneY[i] = waste[i] === 1 ? -0.9 + Math.random() * 0.55 : -0.3 + Math.random() * 1.25;
    drift[i] = (Math.random() - 0.5) * 0.1;
    depth[i] = (Math.random() - 0.5) * 0.6;
  }
  return { phase, laneY, drift, depth, waste };
}

/** smoothstep(0,1,x) — an S-curve, so the peel starts and ends gently. */
function smoothstep(x: number): number {
  const t = Math.min(1, Math.max(0, x));
  return t * t * (3 - 2 * t);
}

function Stream({ share }: { share: number }) {
  const points = useRef<THREE.Points>(null);
  const elapsed = useRef(0);
  const lanes = useMemo(() => makeLanes(share), [share]);

  // Built imperatively rather than with <bufferAttribute> JSX: fewer moving
  // parts, and the colour buffer is written once and never touched again.
  const geometry = useMemo(() => {
    const positions = new Float32Array(COUNT * 3);
    const colors = new Float32Array(COUNT * 3);
    const teal = new THREE.Color(HERO_COLORS.teal);
    const coral = new THREE.Color(HERO_COLORS.coral);

    for (let i = 0; i < COUNT; i += 1) {
      positions[i * 3] = X_START;
      positions[i * 3 + 1] = lanes.laneY[i];
      positions[i * 3 + 2] = lanes.depth[i];
      const color = lanes.waste[i] === 1 ? coral : teal;
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return geo;
  }, [lanes]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame((_state, delta) => {
    // ONE SHOT: past DURATION the buffer is never written again — no loop.
    if (elapsed.current >= DURATION || points.current === null) return;
    elapsed.current = Math.min(DURATION, elapsed.current + delta);

    const attribute = geometry.getAttribute("position") as THREE.BufferAttribute;
    const array = attribute.array as Float32Array;
    const clock = elapsed.current / DURATION;

    for (let i = 0; i < COUNT; i += 1) {
      const phase = lanes.phase[i];
      const progress = Math.min(1, Math.max(0, (clock - phase) / (1 - phase)));
      array[i * 3] = X_START + (X_END - X_START) * progress;

      const peel = lanes.waste[i] === 1 ? smoothstep((progress - SPLIT) / (1 - SPLIT)) : 0;
      array[i * 3 + 1] = lanes.laneY[i] + lanes.drift[i] * progress - 2.2 * peel;
    }

    attribute.needsUpdate = true;
  });

  return (
    <points geometry={geometry} ref={points}>
      <PointMaterial depthWrite={false} size={0.055} sizeAttenuation transparent vertexColors />
    </points>
  );
}

/**
 * The single bold animation in the product: budget flows left to right, the
 * wasted share peels downward in coral, and after ~4s everything stops. No
 * loop, no scroll trigger. Only mounted when the visitor has NOT asked for
 * reduced motion, and only through next/dynamic(ssr:false).
 *
 * Carries the same role="img" + numeric aria-label as FlowStatic (Task 7),
 * worded identically, so a screen-reader visitor gets the same information
 * regardless of which branch Hero picked. The <canvas> itself has no
 * meaningful accessibility tree of its own, so it is aria-hidden — the
 * wrapper's aria-label is the only thing announced.
 */
export default function FlowParticles(props: Props) {
  const { totalSpend, headlineWaste } = props;
  const total = toFiniteNumber(totalSpend);
  const waste = toFiniteNumber(headlineWaste);
  const share = computeCoralShare(props);

  return (
    <div
      aria-label={`Of ${formatPKR(total)} spent, ${formatPKR(waste)} — ${formatPct(
        share * 100,
      )} — is estimated waste.`}
      className="h-full w-full"
      role="img"
    >
      <Canvas
        aria-hidden="true"
        camera={{ fov: 48, position: [0, 0, 7] }}
        dpr={[1, 2]}
        gl={{ alpha: true, antialias: true }}
        style={{ height: "100%", width: "100%" }}
      >
        <Stream share={share} />
      </Canvas>
    </div>
  );
}
