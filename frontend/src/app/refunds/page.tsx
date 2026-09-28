import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "When and how fees paid to Ad Spend Optimization are refunded.",
};

export default function RefundsPage() {
  return (
    <PolicyLayout title="Refund Policy" updated="28 September 2026">
      <section>
        <h2>1. Purchases and refunds</h2>
        <p>
          Refund eligibility and deadlines depend on the offer you purchased and the platform that
          processed your payment. For a purchase made through a marketplace, submit refund requests
          through that marketplace and follow its published process. This product does not itself
          process marketplace purchases or refunds.
        </p>
      </section>
      <section>
        <h2>2. Separately issued invoices</h2>
        <p>
          If we separately issue you an invoice under a written agreement, contact us using the
          address below if you believe it is incorrect or a payment was duplicated. The specific
          invoice and agreement govern any correction or refund.
        </p>
      </section>
      <section>
        <h2>3. Contact</h2>
        <p>
          Email{" "}
          <a className="text-teal underline underline-offset-4" href="mailto:fatimakhalidddd0@gmail.com">
            fatimakhalidddd0@gmail.com
          </a>{" "}
          with your account email and purchase details. We will direct marketplace purchase
          questions to the platform that processed the payment.
        </p>
      </section>
    </PolicyLayout>
  );
}
