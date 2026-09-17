import type { ReactNode } from "react";

export default function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="max-w-xl py-16">
      <h1 className="font-display text-4xl leading-tight">{title}</h1>
      <p className="mt-4 text-slate">{body}</p>
      {action ? <div className="mt-8">{action}</div> : null}
    </div>
  );
}
