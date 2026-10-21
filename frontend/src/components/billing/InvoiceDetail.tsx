"use client";

import CardCheckout from "@/components/billing/CardCheckout";
import PaymentForm from "@/components/billing/PaymentForm";
import PaymentHistory from "@/components/billing/PaymentHistory";
import PaymentInstructions from "@/components/billing/PaymentInstructions";
import StatusPill from "@/components/billing/StatusPill";
import { clampedAmountDue, isOverdue, overpaidBy } from "@/lib/billing";
import { formatMoneyExact, formatPKRExact } from "@/lib/format";
import type { Invoice, PaymentMethod } from "@/lib/types";

type Props = {
  invoice: Invoice;
  methods: PaymentMethod[];
  onSubmitted: () => void;
};

export default function InvoiceDetail({ invoice, methods, onSubmitted }: Props) {
  const payable = invoice.status === "issued" || invoice.status === "payment_submitted";
  const overpaid = overpaidBy(invoice);
  const money = (amount: string) => formatMoneyExact(amount, invoice.currency);
  return (
    <section className="grid gap-6 rounded border border-slate/25 bg-surface p-5">
      <header className="grid gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-display text-xl numeral">{invoice.invoice_number}</h2>
          <StatusPill status={invoice.status} />
          {isOverdue(invoice, new Date()) ? (
            <span className="rounded-full bg-coral/20 px-2 py-0.5 text-xs text-coral">Overdue</span>
          ) : null}
        </div>
        <p className="text-sm text-slate">
          {invoice.period_start} → {invoice.period_end} · due {invoice.due_date}
        </p>
      </header>

      <dl className="grid gap-2 text-sm">
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>Monthly base fee</dt>
          <dd className="numeral">{money(invoice.base_fee)}</dd>
        </div>
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>
            Performance fee on {formatPKRExact(invoice.confirmed_recovered_waste)} recovered
            {invoice.pkr_per_usd ? ` (at ${formatPKRExact(invoice.pkr_per_usd)} per USD)` : null}
          </dt>
          <dd className="numeral">{money(invoice.performance_fee)}</dd>
        </div>
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>Total</dt>
          <dd className="numeral">{money(invoice.total)}</dd>
        </div>
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>Confirmed payments</dt>
          <dd className="numeral">{money(invoice.amount_paid)}</dd>
        </div>
        <div className="flex justify-between font-medium">
          <dt>Still owed</dt>
          <dd className="numeral">{money(clampedAmountDue(invoice))}</dd>
        </div>
        {overpaid ? (
          <div className="flex justify-between font-medium text-teal">
            <dt>Overpaid by</dt>
            <dd className="numeral">{money(overpaid)}</dd>
          </div>
        ) : null}
      </dl>

      <a
        href={`/api/billing/invoices/${invoice.id}/pdf`}
        className="justify-self-start rounded border border-slate/40 px-3 py-1.5 text-sm hover:border-teal hover:text-teal"
      >
        Download PDF
      </a>

      {payable && invoice.pay_by_card && invoice.currency === "USD" ? (
        <CardCheckout invoiceId={invoice.id} amount={money(clampedAmountDue(invoice))} />
      ) : null}

      <div className="grid gap-3">
        <h3 className="font-display text-lg">
          {payable && invoice.pay_by_card ? "Or pay by bank transfer" : "Where to pay"}
        </h3>
        <PaymentInstructions instructions={invoice.instructions} />
      </div>

      <div className="grid gap-3">
        <h3 className="font-display text-lg">Payment history</h3>
        <PaymentHistory payments={invoice.payments} currency={invoice.currency} />
      </div>

      {payable ? (
        <PaymentForm
          invoiceId={invoice.id}
          methods={methods}
          currency={invoice.currency}
          defaultAmount={Number(invoice.amount_due)}
          onSubmitted={onSubmitted}
        />
      ) : null}
    </section>
  );
}
