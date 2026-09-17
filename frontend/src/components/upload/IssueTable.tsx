import type { RowIssue } from "@/lib/types";

type Props = { title: string; issues: RowIssue[]; tone: "error" | "warning" };

/** Hairline dividers, no cell borders — the house table style. */
export default function IssueTable({ title, issues, tone }: Props) {
  if (issues.length === 0) return null;

  return (
    <section className="mt-10">
      <h3 className={`font-display text-lg ${tone === "error" ? "text-coral" : "text-paper"}`}>
        {title} <span className="text-slate">({issues.length})</span>
      </h3>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[30rem] text-sm">
          <thead>
            <tr className="border-b border-slate/20 text-left text-xs uppercase tracking-[0.14em] text-slate">
              <th className="w-28 py-3 pr-4 font-normal" scope="col">
                Where
              </th>
              <th className="w-40 py-3 pr-4 font-normal" scope="col">
                Column
              </th>
              <th className="py-3 font-normal" scope="col">
                Problem
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate/20">
            {issues.map((issue, index) => (
              <tr
                className={tone === "error" ? "text-coral" : "text-slate"}
                key={`${issue.row}-${issue.column}-${index}`}
              >
                <td className="py-3 pr-4 tabular-nums">
                  {issue.row === null ? "Whole file" : `Row ${issue.row}`}
                </td>
                <td className="py-3 pr-4">{issue.column ?? "—"}</td>
                <td className="py-3 text-paper">{issue.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
