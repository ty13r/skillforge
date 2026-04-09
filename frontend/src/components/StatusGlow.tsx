interface StatusGlowProps {
  variant?: "success" | "running" | "warning" | "error" | "neutral";
  className?: string;
}

const COLORS: Record<NonNullable<StatusGlowProps["variant"]>, string> = {
  success: "bg-tertiary text-tertiary",
  running: "bg-secondary text-secondary",
  warning: "bg-warning text-warning",
  error: "bg-error text-error",
  neutral: "bg-on-surface-dim text-on-surface-dim",
};

export default function StatusGlow({
  variant = "neutral",
  className = "",
}: StatusGlowProps) {
  return (
    <span
      className={
        "inline-block h-2 w-2 rounded-full shadow-glow " +
        COLORS[variant] +
        " " +
        className
      }
      aria-hidden="true"
    />
  );
}
