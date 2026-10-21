import type { Metadata } from "next";
import Link from "next/link";

import CinematicHero from "@/components/landing/CinematicHero";
import LandingNav from "@/components/landing/LandingNav";

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
    a: "The analysis runs automatically after you upload a valid CSV. Your report appears as soon as processing completes.",
  },
  {
    q: "Do I pay the performance fee if nothing improves?",
    a: "No. It is charged only on waste that actually goes down from one report to the next, and we agree that figure with you before anything is invoiced.",
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

      {/* Pricing: stated plainly in body copy, after the method — informative, not a sales block.
          Keep in step with NEW_CLIENT_BASE_FEE / NEW_CLIENT_PERFORMANCE_FEE_PCT on the backend. */}
      <section className="border-t border-slate/15" id="pricing">
        <div className="mx-auto max-w-5xl px-6 py-28">
          <h2 className="font-display text-3xl sm:text-4xl">What it costs</h2>
          <p className="mt-6 max-w-2xl font-body leading-relaxed text-slate">
            $65 a month, plus 20% of the ad waste you actually recover — measured by comparing one
            month&rsquo;s report with the next, and agreed with you before it is billed. If nothing
            improves, the monthly fee is all you pay.
          </p>
          <p className="mt-4 max-w-2xl font-body text-sm leading-relaxed text-slate">
            Invoiced monthly in US dollars. Pay by card or bank transfer.
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

      <section className="border-t border-slate/15" id="contact">
        <div className="mx-auto max-w-5xl px-6 py-28">
          <h2 className="max-w-2xl font-display text-3xl leading-tight sm:text-4xl">
            Start analyzing your ad spend.
          </h2>
          <p className="mt-6 max-w-2xl font-body leading-relaxed text-slate">
            Create an account, upload an export, and get a report without sharing access to your ad
            account.
          </p>

          <Link
            className="mt-8 inline-flex items-center justify-center rounded-sm bg-teal px-6 py-3 text-sm font-medium text-ink transition-colors hover:bg-teal/85"
            href="/signup"
          >
            Create account
          </Link>
        </div>
      </section>
    </main>
  );
}
