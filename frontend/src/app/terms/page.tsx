import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern use of the Ad Spend Optimization service.",
};

export default function TermsPage() {
  return (
    <PolicyLayout title="Terms of Service" updated="28 September 2026">
      <section>
        <h2>1. Who we are</h2>
        <p>
          Ad Spend Optimization is operated by Fatima Khalid, trading as a sole proprietor in
          Pakistan. We are not a registered company. For anything to do with these terms, your
          account or your data, write to{" "}
          <a className="text-teal underline underline-offset-4" href="mailto:fatimakhalidddd0@gmail.com">
            fatimakhalidddd0@gmail.com
          </a>
          . A postal address is available on request. In these terms, &ldquo;we&rdquo; and
          &ldquo;us&rdquo; mean that business, and &ldquo;you&rdquo; means the business using the
          service.
        </p>
      </section>
      <section>
        <h2>2. What the service does</h2>
        <p>
          You upload an export of your advertising data. We analyse it, flag segments whose cost per
          conversion is far above your account average, estimate the spend being wasted, and
          recommend budget cuts. Completed reports are available in your account automatically.
        </p>
      </section>
      <section>
        <h2>3. What the analysis is and is not</h2>
        <p>
          The analysis is an estimate produced from the data you supply. It is not a guarantee of any
          result, and it is not advertising, financial or legal advice. Decisions about your budget
          remain yours.
        </p>
        <p>
          We do not need, and will never ask for, access to your advertising account. If anyone
          asks you for your account login or Business Manager access in our name, it is not us.
        </p>
      </section>
      <section>
        <h2>4. Your account</h2>
        <p>
          You are responsible for keeping your password safe and for everything done through your
          account. Tell us immediately if you believe someone else has access.
        </p>
      </section>
      <section>
        <h2>5. Your data</h2>
        <p>
          You keep ownership of everything you upload. You confirm you are allowed to share it with
          us. How we handle it is described in our Privacy Policy.
        </p>
      </section>
      <section>
        <h2>6. Account access and offers</h2>
        <p>
          Creating an account lets you use the analysis features. Pricing, access duration, and any
          usage or feature limits are set out in the offer through which you purchase access; account
          creation alone does not confirm a paid purchase or change those terms.
        </p>
      </section>
      <section>
        <h2>7. Fees and payment</h2>
        <p>
          Any price, billing schedule, renewal, or payment terms are those shown by the purchase
          offer and the platform that processes it. We do not collect payment details when you create
          an account. If we separately issue an invoice under a written agreement, its stated terms
          apply to that invoice.
        </p>
      </section>
      <section>
        <h2>8. Ending the agreement</h2>
        <p>
          Cancellation, expiry, and continued access are governed by the offer through which you
          purchased access. You can request deletion of your uploads and reports as described in the
          Privacy Policy. Records we are legally required to retain may be kept for the applicable
          period.
        </p>
      </section>
      <section>
        <h2>9. Limits on our liability</h2>
        <p>
          The service tells you what we think your data shows. It cannot know your business, your
          margins or your reasons for running a campaign, so acting on a recommendation is your
          decision and your risk.
        </p>
        <p>
          We are not liable for lost profits, lost sales or lost advertising results arising from
          decisions you make on the basis of a report. Where we are liable for anything else, our
          total liability is limited to the fees you paid us in the three months before the problem
          arose. Nothing here limits liability that cannot lawfully be limited, including liability
          for fraud.
        </p>
      </section>
      <section>
        <h2>10. Changes to these terms</h2>
        <p>
          If we change these terms, we will email you at least 14 days before the change takes
          effect. If you do not agree with a change, you can end the agreement under clause 8 before
          it applies to you.
        </p>
      </section>
      <section>
        <h2>11. Governing law</h2>
        <p>
          These terms are governed by the laws of Pakistan, and the courts of Pakistan have
          jurisdiction over any dispute. Before going to court, both of us agree to raise the
          problem in writing and give the other 14 days to put it right.
        </p>
      </section>
    </PolicyLayout>
  );
}
