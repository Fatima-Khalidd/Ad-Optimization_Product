import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What data the Ad Spend Optimization service collects and how it is handled.",
};

export default function PrivacyPage() {
  return (
    <PolicyLayout title="Privacy Policy" updated="TODO-OWNER: effective date">
      <section>
        <h2>1. Who controls your data</h2>
        <p>TODO-OWNER: registered business name, address, and a privacy contact email.</p>
      </section>
      <section>
        <h2>2. What we collect</h2>
        <p>
          Your account details (business name, email address, and a hashed password — we never store
          the password itself); the advertising exports you upload; the reports generated from them;
          your invoices; and the payment details you submit, which are a method, a transaction
          reference, an amount, a date, and an optional screenshot.
        </p>
      </section>
      <section>
        <h2>3. Why we hold it</h2>
        <p>
          To run the analysis you asked for, to show you your reports, to invoice you, to confirm
          payments you tell us about, and to keep an audit trail so any billing dispute can be
          settled from records rather than memory.
        </p>
      </section>
      <section>
        <h2>4. Where it is stored</h2>
        <p>
          In a managed PostgreSQL database and a private file store hosted in the Mumbai
          (ap-south-1) region. Uploaded files and payment screenshots are never publicly
          accessible, and are only served back to the account that owns them.
        </p>
      </section>
      <section>
        <h2>5. Who else sees it</h2>
        <p>
          Our hosting, database and error-reporting providers, acting on our instructions. We do not
          sell your data and we do not use it to train anything. TODO-OWNER: list the providers by
          name once the production accounts are created.
        </p>
      </section>
      <section>
        <h2>6. How long we keep it</h2>
        <p>TODO-OWNER: retention period for uploads, reports and invoices, and what deletion covers.</p>
      </section>
      <section>
        <h2>7. Your rights</h2>
        <p>
          You can ask for a copy of your data, ask us to correct it, or ask us to delete it. Write to
          the privacy contact above. TODO-OWNER: the response time you commit to.
        </p>
      </section>
      <section>
        <h2>8. Cookies</h2>
        <p>
          We set two cookies, both strictly necessary: one short-lived session cookie and one refresh
          cookie, used only to keep you signed in. There is no advertising or tracking cookie.
        </p>
      </section>
    </PolicyLayout>
  );
}
