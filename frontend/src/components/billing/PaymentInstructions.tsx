"use client";

import { useState } from "react";

import { METHOD_LABELS } from "@/lib/billing";
import type { PaymentInstruction } from "@/lib/types";

export default function PaymentInstructions({ instructions }: { instructions: PaymentInstruction[] }) {
  const [copied, setCopied] = useState<string | null>(null);

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(null); // clipboard blocked (http, or permission denied) — the number is on screen anyway
    }
  }

  if (instructions.length === 0) {
    return <p className="text-slate">No payment accounts are set up yet — contact us before paying.</p>;
  }

  return (
    <ul className="grid gap-3">
      {instructions.map((instruction) => (
        <li key={`${instruction.method_type}-${instruction.account_identifier}`} className="border-b border-slate/15 pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{METHOD_LABELS[instruction.method_type]}</span>
            <span className="numeral">{instruction.account_identifier}</span>
            <button
              type="button"
              onClick={() => copy(instruction.account_identifier)}
              className="rounded border border-slate/40 px-2 py-0.5 text-xs text-slate hover:border-teal hover:text-teal"
            >
              {copied === instruction.account_identifier ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="text-sm text-slate">{instruction.account_title}</p>
          {instruction.instructions ? <p className="text-sm text-slate">{instruction.instructions}</p> : null}
        </li>
      ))}
    </ul>
  );
}
