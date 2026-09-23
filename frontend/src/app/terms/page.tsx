import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern use of the Ad Spend Optimization service.",
};

export default function TermsPage() {
  return (
    <PolicyLayout title="Terms of Service" updated="23 September 2026">
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
          recommend budget cuts. Every report is reviewed by us before you see it.
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
        <h2>6. Free audits</h2>
        <p>
          We sometimes run a first analysis free of charge, to show you what the service produces.
          A free audit carries no fee and no obligation to continue. You can ask us to delete the
          file you sent and the report it produced at any time, and we will.
        </p>
      </section>
      <section>
        <h2>7. Fees and payment</h2>
        <p>
          Fees are a monthly base fee plus a performance fee. The base fee covers running the
          analysis and is charged monthly. The performance fee is a percentage of recovered waste —
          money you were previously spending on flagged segments and no longer are, measured by
          comparing the same segments before and after you acted.
        </p>
        <p>
          The exact base fee and percentage are the ones written in your own agreement with us, and
          they do not change without your written consent. A performance fee is only ever charged on
          recovery we have confirmed with you first; it is never calculated automatically and
          invoiced without you seeing it. If nothing was recovered in a period, no performance fee
          is charged for that period.
        </p>
        <p>
          Invoices are due within 14 days of being issued. Payment is made to the accounts listed on
          the invoice — JazzCash, Easypaisa, NayaPay, or a bank transfer via Raast or IBAN — after
          which you submit the transaction reference. Submitting a reference is a claim that you
          have paid; an invoice is only marked paid once we have verified the money against our own
          records.
        </p>
      </section>
      <section>
        <h2>8. Ending the agreement</h2>
        <p>
          Either of us can end the agreement by giving 14 days&rsquo; notice in writing, including by
          email. There is no minimum term and no cancellation charge. Invoices already issued for
          work already done remain payable, and any performance fee for recovery already confirmed
          remains payable. We will not issue new invoices after the notice period ends.
        </p>
        <p>
          On request after you leave, we will delete your uploads and reports. We keep invoices and
          payment records for as long as the law requires — see the Privacy Policy.
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
