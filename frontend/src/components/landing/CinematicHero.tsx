"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/motion";

export const HERO_POSTER = "/hero/flow-poster.jpg";
export const HERO_VIDEO = "/hero/flow.mp4";

/**
 * The landing hero. The film is decoration, not information: the headline,
 * the sub-line and the calls to action are plain DOM and are readable with
 * the video missing, blocked, still downloading, or refused because the
 * visitor asked for reduced motion. Three things can go wrong and all three
 * land on the same still frame:
 *
 *   1. prefers-reduced-motion  -> we never attach the <video> at all
 *   2. the file 404s / codec unsupported -> onError drops back to the poster
 *   3. autoplay is refused (some mobile power-saving modes) -> the poster is
 *      already painted underneath, so the visitor sees the frame, not a void
 *
 * The poster image is a real frame of the film, so every one of those paths
 * looks deliberate rather than broken.
 */
export default function CinematicHero() {
  const reduced = useReducedMotion();
  const [failed, setFailed] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const showVideo = !reduced && !failed;

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    // Safari/iOS can ignore the autoPlay attribute when the element is
    // mounted by hydration rather than parsed from the document. A refused
    // play() is not an error here — the poster is already showing.
    void el.play().catch(() => undefined);
  }, [showVideo]);

  return (
    <section className="relative isolate flex min-h-[92vh] flex-col justify-center overflow-hidden">
      {/* The still frame sits under everything, always. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-20 bg-ink bg-cover bg-center"
        style={{ backgroundImage: `url(${HERO_POSTER})` }}
      />

      {showVideo ? (
        <video
          ref={videoRef}
          aria-hidden="true"
          autoPlay
          className="absolute inset-0 -z-20 h-full w-full object-cover"
          data-testid="hero-video"
          loop
          muted
          onError={() => setFailed(true)}
          playsInline
          poster={HERO_POSTER}
          preload="auto"
        >
          <source src={HERO_VIDEO} type="video/mp4" />
        </video>
      ) : null}

      {/* Scrim. Without it the headline sits on moving particles and becomes
          unreadable exactly when the stream passes behind it. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-gradient-to-r from-ink via-ink/85 to-ink/45"
      />
      <div
        aria-hidden="true"
        className="absolute inset-x-0 bottom-0 -z-10 h-48 bg-gradient-to-t from-ink to-transparent"
      />

      <div className="mx-auto w-full max-w-5xl px-6 py-24">
        <p className="text-xs uppercase tracking-[0.25em] text-teal">
          Ad Spend Optimization
        </p>
        <h1 className="mt-6 max-w-3xl font-display text-5xl leading-[1.05] sm:text-6xl lg:text-7xl">
          Find the money leaking out of your ads.
        </h1>
        <p className="mt-8 max-w-xl font-body text-lg leading-relaxed text-slate">
          Upload one export. We measure every placement, age group and time slot against your
          own account average and show you, in rupees, exactly where the budget is going
          nowhere.
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Link
            className="inline-flex items-center justify-center rounded-sm bg-teal px-6 py-3 text-sm font-medium text-ink transition-colors hover:bg-teal/85"
            href="/signup"
          >
            Create an account
          </Link>
          <Link
            className="inline-flex items-center justify-center rounded-sm border border-slate/40 px-6 py-3 text-sm font-medium text-paper transition-colors hover:border-slate"
            href="#how-it-works"
          >
            See how it works
          </Link>
        </div>

        <p className="mt-8 text-sm text-slate">
          Built for businesses spending Rs. 100,000&ndash;500,000 a month on Meta and Google.
        </p>
      </div>
    </section>
  );
}
