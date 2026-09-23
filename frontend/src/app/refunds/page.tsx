import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "When and how fees paid to Ad Spend Optimization are refunded.",
};

export default function RefundsPage() {
  return (
    <PolicyLayout title="Refund Policy" updated="23 September 2026">
      <section>
        <h2>1. How you pay</h2>
        <p>
          Invoices are paid manually to the accounts listed on the invoice: JazzCash, Easypaisa,
          NayaPay, or a bank transfer via Raast or IBAN. After paying, you submit the transaction ID
          on your billing page, and we confirm it against our own records before the invoice is
          marked paid.
        </p>
      </section>
      <section>
        <h2>2. If you were charged the wrong amount</h2>
        <p>
          Performance fees are based on recovered waste that we calculate and then confirm before
          issuing an invoice. If you believe the figure is wrong, raise it and we will re-check it
          against the stored report and its configuration snapshot. Please raise a billing query
          within 30 days of the invoice date, while the underlying data is easy to reconstruct.
        </p>
        <p>
          If the re-check shows we overcharged you, we refund the difference within 7 working days,
          or credit it against your next invoice if you prefer. If the invoice is unpaid, we cancel
          it and reissue a corrected one.
        </p>
      </section>
      <section>
        <h2>3. Duplicate or failed payments</h2>
        <p>
          If a payment reaches us twice, or reaches us for an invoice that was already settled, we
          refund the surplus to the account it came from within 7 working days of spotting it or
          being told about it, whichever comes first.
        </p>
      </section>
      <section>
        <h2>4. Monthly fees already paid</h2>
        <p>
          The base fee pays for that month&rsquo;s analysis. Once we have delivered a report for the
          month, the base fee for that month is not refundable — the work is done and cannot be
          returned. If we did not deliver a report in a month you were charged for, we refund that
          month&rsquo;s base fee in full.
        </p>
        <p>
          If you cancel partway through a month, you are not charged for the following month. We do
          not pro-rate part-months in either direction, because the analysis either ran or it did
          not.
        </p>
      </section>
      <section>
        <h2>5. If the analysis finds nothing</h2>
        <p>
          Some accounts are already well run, and a report that finds little or no waste is a valid
          result, not a failure. The base fee still applies, because the work was done. No
          performance fee is charged, because nothing was recovered.
        </p>
      </section>
      <section>
        <h2>6. How to request a refund</h2>
        <p>
          Email{" "}
          <a className="text-teal underline underline-offset-4" href="mailto:fatimakhalidddd0@gmail.com">
            fatimakhalidddd0@gmail.com
          </a>{" "}
          with the invoice number, the transaction ID you submitted, the amount, and one line on
          what went wrong. We will reply within 7 days. Refunds go back to the same account the
          payment came from — we cannot send a refund to a different account.
        </p>
      </section>
    </PolicyLayout>
  );
}
