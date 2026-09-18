import { METHOD_LABELS } from "@/lib/billing";
import { formatPKRExact } from "@/lib/format";
import type { Payment } from "@/lib/types";

const PAYMENT_TONE: Record<Payment["status"], string> = {
  pending: "text-slate",
  confirmed: "text-teal",
  rejected: "text-coral",
};

const PAYMENT_LABEL: Record<Payment["status"], string> = {
  pending: "Awaiting review",
  confirmed: "Confirmed",
  rejected: "Rejected",
};

export default function PaymentHistory({ payments }: { payments: Payment[] }) {
  if (payments.length === 0) {
    return <p className="text-slate">No payments reported yet.</p>;
  }
  return (
    <ul className="grid gap-2 text-sm">
      {payments.map((payment) => (
        <li key={payment.id} className="border-b border-slate/15 pb-2">
          <div className="flex flex-wrap justify-between gap-2">
            <span className="numeral">
              {METHOD_LABELS[payment.method_type]} · {payment.transaction_ref}
            </span>
            <span className="numeral">{formatPKRExact(payment.amount)}</span>
          </div>
          <div className="flex flex-wrap justify-between gap-2 text-xs">
            <span className="text-slate">
              Paid {payment.paid_at}
              {payment.has_proof ? " · proof attached" : ""}
              {payment.status === "pending" ? " · awaiting our check, not yet applied to the invoice" : ""}
            </span>
            <span className={PAYMENT_TONE[payment.status]}>{PAYMENT_LABEL[payment.status]}</span>
          </div>
          {payment.status === "rejected" && payment.review_note ? (
            <p className="text-xs text-coral">Rejected: {payment.review_note}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
