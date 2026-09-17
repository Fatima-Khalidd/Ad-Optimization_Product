import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" };

/** transition-colors is the only hover effect allowed anywhere in the product. */
export default function Button({ variant = "primary", className = "", ...rest }: Props) {
  const base =
    "inline-flex items-center justify-center rounded-sm px-5 py-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const look =
    variant === "primary"
      ? "bg-teal text-ink hover:bg-teal/85"
      : "border border-slate/40 text-paper hover:border-slate";
  return <button className={`${base} ${look} ${className}`} {...rest} />;
}
