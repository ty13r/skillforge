interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  accent?: "primary" | "secondary" | "tertiary";
}

const ACCENT_BORDER: Record<NonNullable<StatCardProps["accent"]>, string> = {
  primary: "before:bg-primary",
  secondary: "before:bg-secondary",
  tertiary: "before:bg-tertiary",
};

export default function StatCard({
  label,
  value,
  hint,
  accent = "primary",
}: StatCardProps) {
  return (
    <div
      className={
        "relative overflow-hidden rounded-xl bg-surface-container-low p-5 " +
        "before:absolute before:left-0 before:top-0 before:h-full before:w-1 " +
        ACCENT_BORDER[accent]
      }
    >
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        {label}
      </p>
      <p className="mt-2 font-display text-3xl tracking-tight text-on-surface">
        {value}
      </p>
      {hint && (
        <p className="mt-1 text-xs text-on-surface-dim">{hint}</p>
      )}
    </div>
  );
}
