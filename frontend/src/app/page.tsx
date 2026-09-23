import type { Metadata } from "next";
import Link from "next/link";

import CinematicHero from "@/components/landing/CinematicHero";
import LandingNav from "@/components/landing/LandingNav";
import { AUDIT_CONTACT_HREF, AUDIT_CTA_LABEL } from "@/lib/contact";

export const metadata: Metadata = {
  title: "Ad Spend Optimization — find the waste in your ad budget",
  description:
    "Upload one ad export and see which placements, age groups and time slots are spending above your own account average — in rupees, with the arithmetic shown.",
};

const STEPS = [
  {
    n: "01",
    title: "Upload one export",
    body: "A CSV from Meta or Google Ads — one row per segment per day. Nothing to install, and you never hand over access to your ad account.",
  },
  {
    n: "02",
    title: "Every segment gets measured",
    body: "We work out the cost per conversion for each placement, age group and time slot, then compare each one against your own account average.",
  },
  {
    n: "03",
    title: "You get a report you can act on",
    body: "Each flagged segment comes with the numbers behind it and a specific amount to cut. Download it as a PDF and hand it to whoever runs your ads.",
  },
] as const;

const DIMENSIONS = [
  {
    title: "Placement",
    body: "Facebook feed, Instagram feed, Stories, Audience Network. One placement quietly costing three times the rest is the most common leak we see.",
  },
  {
    title: "Age group",
    body: "Budget spread evenly across age brackets that convert nothing like evenly. The same campaign, cut a different way.",
  },
  {
    title: "Time of day",
    body: "Overnight impressions that cost the same as midday ones and convert at a fraction of the rate.",
  },
] as const;

const METHOD = [
  {
    title: "Your account is its own benchmark",
    body: "A segment is flagged when its cost per conversion runs well above the average for your account — not against industry figures nobody can check.",
  },
  {
    title: "We never add the three views together",
    body: "The same wasted rupee shows up in the placement view, the age view and the time-of-day view. Summing them would overstate your waste threefold, so we always report the largest single view.",
  },
  {
    title: "Thin segments are held back",
    body: "A segment with very little spend or almost no conversions can look terrible on noise alone. Those are shown to you, but never flagged as waste.",
  },
  {
    title: "Every report is reproducible",
    body: "Each analysis stores the exact settings it ran with, so a report can be rebuilt and checked months later — and every figure traces back to rows you uploaded.",
  },
] as const;

const FAQ = [
  {
    q: "Do you need access to my ad account?",
    a: "No. A CSV export is enough. Nothing is connected, and no credentials change hands.",
  },
  {
    q: "Is this AI?",
    a: "No. It is arithmetic — cost per conversion per segment, compared against your account average. We think that is the point: every number in a report can be traced back to the rows you uploaded, which is not true of a model that guesses.",
  },
  {
    q: "What does the file need to contain?",
    a: "Date, campaign, placement, age group, time slot, spend, impressions, clicks and conversions. If columns are missing or malformed we tell you which rows and why, before anything is analysed.",
  },
  {
    q: "How long does it take?",
    a: "The analysis itself runs in seconds. Every report is then checked by a person before it reaches you, so nothing lands in your dashboard unreviewed.",
  },
  {
    q: "How do I pay?",
    a: "JazzCash, Easypaisa, NayaPay or a bank transfer over Raast. You send the payment and submit the transaction ID; we confirm it against the account. No card, no gateway.",
  },
] as const;

export default function Home() {
  return (
    <main className="relative">
      <LandingNav />
      <CinematicHero />

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-6 py-28" id="how-it-works">
        <h2 className="font-display text-3xl sm:text-4xl">Three steps, one file</h2>
        <div className="mt-14 grid gap-12 md:grid-cols-3">
          {STEPS.map((step) => (
            <div key={step.n}>
              <p className="font-display text-sm tracking-[0.2em] text-teal">{step.n}</p>
              <h3 className="mt-4 font-display text-xl">{step.title}</h3>
              <p className="mt-3 font-body leading-relaxed text-slate">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* What gets measured */}
      <section className="border-t border-slate/15">
        <div className="mx-auto max-w-5xl px-6 py-28">
          <h2 className="font-display text-3xl sm:text-4xl">The same budget, cut three ways</h2>
          <p className="mt-6 max-w-2xl font-body leading-relaxed text-slate">
            A campaign-level report tells you a campaign is underperforming. It does not tell you
            which part of it. We break the same spend down along three dimensions, so the fix is
            a setting you can actually change.
          </p>
          <div className="mt-14 grid gap-12 md:grid-cols-3">
            {DIMENSIONS.map((dimension) => (
              <div key={dimension.title}>
                <h3 className="font-display text-xl">{dimension.title}</h3>
                <p className="mt-3 font-body leading-relaxed text-slate">{dimension.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Method */}
      <section className="border-t border-slate/15" id="method">
        <div className="mx-auto max-w-5xl px-6 py-28">
          <h2 className="font-display text-3xl sm:text-4xl">No black box</h2>
          <p className="mt-6 max-w-2xl font-body leading-relaxed text-slate">
            You are going to be asked to cut spend on the strength of these numbers, so you should
            be able to check them. Here is exactly what we do and what we refuse to do.
          </p>
          <div className="mt-14 grid gap-x-12 gap-y-12 md:grid-cols-2">
            {METHOD.map((item) => (
              <div key={item.title}>
                <h3 className="font-display text-xl">{item.title}</h3>
                <p className="mt-3 font-body leading-relaxed text-slate">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="border-t border-slate/15" id="pricing">
        <div className="mx-auto max-w-5xl px-6 py-28">
          <h2 className="font-display text-3xl sm:text-4xl">You pay a share of what you save</h2>
          <div className="mt-12 grid gap-12 md:grid-cols-2">
            <div>
              <h3 className="font-display text-xl">A small monthly base fee</h3>
              <p className="mt-3 font-body leading-relaxed text-slate">
                Covers the analysis itself — every upload, every report, every dimension, as often
                as you want to run it.
              </p>
            </div>
            <div>
              <h3 className="font-display text-xl">Plus a share of recovered waste</h3>
              <p className="mt-3 font-body leading-relaxed text-slate">
                Charged only on waste you actually recover, measured by comparing the flagged
                segments before and after you act — and confirmed by a person before it ever
                reaches an invoice. If nothing is recovered, there is nothing to charge.
              </p>
            </div>
          </div>
          <p className="mt-12 max-w-2xl font-body leading-relaxed text-slate">
            Payment is by JazzCash, Easypaisa, NayaPay or a bank transfer over Raast. You submit
            the transaction ID and we confirm it — submitting an ID is a claim, not a payment, and
            an invoice is only marked paid once the money is verified.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-slate/15">
        <div className="mx-auto max-w-5xl px-6 py-28">
          <h2 className="font-display text-3xl sm:text-4xl">Questions</h2>
          <dl className="mt-14 grid gap-10 md:grid-cols-2">
            {FAQ.map((item) => (
              <div key={item.q}>
                <dt className="font-display text-lg">{item.q}</dt>
                <dd className="mt-3 font-body leading-relaxed text-slate">{item.a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* Close */}
      <section className="border-t border-slate/15">
        <div className="mx-auto max-w-5xl px-6 py-28">
          <h2 className="max-w-2xl font-display text-3xl leading-tight sm:text-4xl">
            Find out what your account is wasting.
          </h2>
          <p className="mt-6 max-w-2xl font-body leading-relaxed text-slate">
            We are taking on a small number of businesses for a free first audit &mdash; you send
            one export, we send back the report and walk you through it. No fee and no obligation
            to continue.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <a
              className="inline-flex items-center justify-center rounded-sm bg-teal px-6 py-3 text-sm font-medium text-ink transition-colors hover:bg-teal/85"
              href={AUDIT_CONTACT_HREF}
            >
              {AUDIT_CTA_LABEL}
            </a>
            <Link
              className="inline-flex items-center justify-center rounded-sm border border-slate/40 px-6 py-3 text-sm font-medium text-paper transition-colors hover:border-slate"
              href="/login"
            >
              Existing client? Sign in
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
