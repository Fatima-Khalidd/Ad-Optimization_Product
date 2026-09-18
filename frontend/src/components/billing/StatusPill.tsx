import { STATUS_LABELS, STATUS_PILL } from "@/lib/billing";
import type { InvoiceStatus } from "@/lib/types";

export default function StatusPill({ status }: { status: InvoiceStatus }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${STATUS_PILL[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
