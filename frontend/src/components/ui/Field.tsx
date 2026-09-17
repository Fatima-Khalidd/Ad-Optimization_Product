type Props = {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  autoComplete?: string;
  minLength?: number;
};

/** Label and input are wired by id so getByLabelText finds the control. */
export default function Field({ label, name, type = "text", required = true, autoComplete, minLength }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs uppercase tracking-[0.18em] text-slate" htmlFor={name}>
        {label}
      </label>
      <input
        className="rounded-sm border border-slate/30 bg-surface px-4 py-3 text-paper outline-none transition-colors focus:border-teal focus-visible:ring-1 focus-visible:ring-teal"
        id={name}
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
        minLength={minLength}
      />
    </div>
  );
}
