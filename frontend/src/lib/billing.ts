import type { Invoice, InvoiceStatus, MethodType } from "@/lib/types";

export const METHOD_LABELS: Record<MethodType, string> = {
  jazzcash: "JazzCash",
  easypaisa: "Easypaisa",
  nayapay: "NayaPay",
  raast: "Raast",
  bank_iban: "Bank transfer (IBAN)",
};

export const STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "Draft",
  issued: "Unpaid",
  payment_submitted: "Awaiting confirmation",
  paid: "Paid",
  void: "Void",
};

export const STATUS_PILL: Record<InvoiceStatus, string> = {
  draft: "bg-slate/20 text-slate",
  issued: "bg-slate/20 text-paper",
  payment_submitted: "bg-teal/20 text-teal",
  paid: "bg-teal text-ink",
  void: "bg-slate/20 text-slate",
};

/** The viewer's local calendar date as YYYY-MM-DD. `toISOString()` would shift by the UTC offset. */
export function toISODate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Past the due date and still owed. Both sides are YYYY-MM-DD, so a string compare is a date compare. */
export function isOverdue(invoice: Pick<Invoice, "due_date" | "status">, today: Date): boolean {
  if (invoice.status === "paid" || invoice.status === "void" || invoice.status === "draft") return false;
  return invoice.due_date < toISODate(today);
}

export function amountDue(invoice: Pick<Invoice, "total" | "amount_paid">): number {
  return Number(invoice.total) - Number(invoice.amount_paid);
}
