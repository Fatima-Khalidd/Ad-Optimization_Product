import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What data the Ad Spend Optimization service collects and how it is handled.",
};

export default function PrivacyPage() {
  return (
    <PolicyLayout title="Privacy Policy" updated="23 September 2026">
      <section>
        <h2>1. Who controls your data</h2>
        <p>
          Ad Spend Optimization, operated by Fatima Khalid, a sole proprietor in Pakistan. For any
          privacy question, or to ask for a copy of your data or its deletion, write to{" "}
          <a className="text-teal underline underline-offset-4" href="mailto:fatimakhalidddd0@gmail.com">
            fatimakhalidddd0@gmail.com
          </a>
          . A postal address is available on request.
        </p>
      </section>
      <section>
        <h2>2. What we collect</h2>
        <p>
          Your account details (business name, email address, and a hashed password — we never store
          the password itself); the advertising exports you upload; the reports generated from them;
          your invoices; and the payment details you submit, which are a method, a transaction
          reference, an amount, a date, and an optional screenshot.
        </p>
        <p>
          The exports are advertising performance figures — spend, impressions, clicks and
          conversions, broken down by placement, age group and time of day. They are not your
          customers&rsquo; personal details, and the analysis does not need them. If your export
          contains anything identifying an individual, you can remove it before sending; nothing we
          do depends on it.
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
        <p>
          If you send us an export by email or WhatsApp — for a free audit, for example — that file
          also sits in that mailbox and on our own computer. We delete it on request, and we delete
          it by default once the audit it was sent for is finished and delivered.
        </p>
      </section>
      <section>
        <h2>5. Who else sees it</h2>
        <p>
          No one, other than the service providers that run the software on our instructions:
          Vercel (website hosting), Railway and Supabase (the application, its database and its file
          storage, in the Mumbai region), and Sentry (error reporting, which records technical
          faults and does not receive your advertising data). We do not sell your data, we do not
          share it with other clients, and we do not use it to train any model. If we change
          provider, we will update this list.
        </p>
      </section>
      <section>
        <h2>6. How long we keep it</h2>
        <p>
          Uploads and the reports made from them: 24 months, so that year-on-year comparisons are
          possible. Invoices and payment records: 6 years, because tax and accounting rules require
          it. Account details: until you close your account.
        </p>
        <p>
          When you ask us to delete something, we delete the uploaded file, the report and the
          analysis behind it. We keep invoices and payment records for the period above even after
          deletion, because we are required to — but those contain amounts and dates, not your
          advertising data.
        </p>
      </section>
      <section>
        <h2>7. Your rights</h2>
        <p>
          You can ask for a copy of your data, ask us to correct it, or ask us to delete it. Write to
          the privacy contact above. We will reply within 7 days and complete the request within 30
          days. There is no charge.
        </p>
      </section>
      <section>
        <h2>8. Cookies</h2>
        <p>
          We set two cookies, both strictly necessary: one short-lived session cookie and one refresh
          cookie, used only to keep you signed in. There is no advertising or tracking cookie.
        </p>
      </section>
      <section>
        <h2>9. Changes to this policy</h2>
        <p>
          If we change how we handle your data in a way that affects you, we will email you before
          the change takes effect. The date at the top of this page always shows when it last
          changed.
        </p>
      </section>
    </PolicyLayout>
  );
}
