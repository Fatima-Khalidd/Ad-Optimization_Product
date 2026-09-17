"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { formatPKR, humanizeSegment } from "@/lib/format";
import { useReducedMotion } from "@/lib/motion";
import { DIMENSION_LABELS, type RecommendationOut } from "@/lib/types";

/**
 * The only Framer Motion in the product, and it only ever runs because the
 * visitor clicked a button — no scroll triggers, no hover animation. When
 * prefers-reduced-motion is set, the expanded content mounts immediately
 * with no animation, rather than skipping the click's effect entirely.
 */
export default function RecommendationList({ recommendations }: { recommendations: RecommendationOut[] }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const reducedMotion = useReducedMotion();

  if (recommendations.length === 0) {
    return (
      <p className="mt-6 max-w-xl text-slate">
        Nothing to cut this period — No segment is spending above the benchmark by enough to flag.
      </p>
    );
  }

  return (
    <ul className="mt-6 divide-y divide-slate/20 border-t border-slate/20">
      {recommendations.map((recommendation) => {
        const open = openId === recommendation.id;
        const panelId = `recommendation-${recommendation.id}`;

        return (
          <li key={recommendation.id}>
            <button
              aria-controls={panelId}
              aria-expanded={open}
              className="flex w-full flex-wrap items-baseline justify-between gap-x-6 gap-y-2 py-5 text-left"
              onClick={() => setOpenId(open ? null : recommendation.id)}
              type="button"
            >
              <span>
                <span className="font-display text-lg">{humanizeSegment(recommendation.segment_name)}</span>
                <span className="ml-3 text-xs uppercase tracking-[0.14em] text-slate">
                  {DIMENSION_LABELS[recommendation.dimension]}
                </span>
              </span>
              <span className="whitespace-nowrap font-display text-lg text-coral">
                Cut {formatPKR(recommendation.recommended_cut)}
              </span>
            </button>

            {reducedMotion ? (
              open ? (
                <div className="overflow-hidden" id={panelId}>
                  <div className="flex flex-col gap-2 pb-6">
                    <p className="max-w-2xl text-slate">{recommendation.reason}</p>
                    <p className="text-xs uppercase tracking-[0.14em] text-slate">
                      Currently spending {formatPKR(recommendation.current_spend)}
                    </p>
                  </div>
                </div>
              ) : null
            ) : (
              <AnimatePresence initial={false}>
                {open ? (
                  <motion.div
                    animate={{ height: "auto", opacity: 1 }}
                    className="overflow-hidden"
                    exit={{ height: 0, opacity: 0 }}
                    id={panelId}
                    initial={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.22, ease: "easeOut" }}
                  >
                    <div className="flex flex-col gap-2 pb-6">
                      <p className="max-w-2xl text-slate">{recommendation.reason}</p>
                      <p className="text-xs uppercase tracking-[0.14em] text-slate">
                        Currently spending {formatPKR(recommendation.current_spend)}
                      </p>
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            )}
          </li>
        );
      })}
    </ul>
  );
}
