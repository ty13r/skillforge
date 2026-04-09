interface StatusGlowProps {
  variant?: "success" | "running" | "warning" | "error" | "neutral";
  className?: string;
  /** When true, the dot pulses to indicate active state. Defaults to true for "running" and "warning". */
  pulse?: boolean;
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
  pulse,
}: StatusGlowProps) {
  const shouldPulse =
    pulse ?? (variant === "running" || variant === "warning");
  return (
    <span
      className={
        "inline-block h-2 w-2 rounded-full shadow-glow " +
        COLORS[variant] +
        (shouldPulse ? " animate-pulse-glow" : "") +
        " " +
        className
      }
      aria-hidden="true"
    />
  );
}
