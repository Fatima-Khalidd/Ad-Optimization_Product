import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern use of the Ad Spend Optimization service.",
};

export default function TermsPage() {
  return (
    <PolicyLayout title="Terms of Service" updated="TODO-OWNER: effective date">
      <section>
        <h2>1. Who we are</h2>
        <p>TODO-OWNER: registered business name, address, and the contact email clients should use.</p>
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
        <h2>6. Fees and payment</h2>
        <p>
          Fees are a monthly base fee plus a performance fee calculated on recovered waste that we
          confirm with you before invoicing. TODO-OWNER: the base fee amount, the performance
          percentage, any cap, and the payment window in days.
        </p>
      </section>
      <section>
        <h2>7. Ending the agreement</h2>
        <p>TODO-OWNER: notice period, and what happens to invoices already issued.</p>
      </section>
      <section>
        <h2>8. Limits on our liability</h2>
        <p>TODO-OWNER: liability cap and exclusions, checked by a lawyer before launch.</p>
      </section>
      <section>
        <h2>9. Governing law</h2>
        <p>TODO-OWNER: governing law and the courts that have jurisdiction.</p>
      </section>
    </PolicyLayout>
  );
}
