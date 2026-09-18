import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "When and how fees paid to Ad Spend Optimization are refunded.",
};

export default function RefundsPage() {
  return (
    <PolicyLayout title="Refund Policy" updated="TODO-OWNER: effective date">
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
          against the stored report and its configuration snapshot. TODO-OWNER: the window in days
          for raising a billing query.
        </p>
      </section>
      <section>
        <h2>3. Duplicate or failed payments</h2>
        <p>
          If a payment reaches us twice, or reaches us for an invoice that was already settled, we
          refund the surplus to the account it came from. TODO-OWNER: how many working days that
          takes.
        </p>
      </section>
      <section>
        <h2>4. Monthly fees already paid</h2>
        <p>TODO-OWNER: whether a paid month is refundable, pro-rated, or non-refundable, and why.</p>
      </section>
      <section>
        <h2>5. How to request a refund</h2>
        <p>
          TODO-OWNER: the email address to write to, and what to include — invoice number,
          transaction ID, and the amount.
        </p>
      </section>
    </PolicyLayout>
  );
}
