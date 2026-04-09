import type { ReactNode } from "react";

interface ModeCardProps {
  title: string;
  description: string;
  selected: boolean;
  disabled?: boolean;
  badge?: string;
  icon: ReactNode;
  onClick?: () => void;
}

export default function ModeCard({
  title,
  description,
  selected,
  disabled = false,
  badge,
  icon,
  onClick,
}: ModeCardProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={
        "relative flex w-full flex-col items-start gap-2 rounded-xl p-5 text-left transition-all " +
        (selected
          ? "bg-surface-container-high shadow-[0_0_0_1px_rgba(192,193,255,0.6)]"
          : "bg-surface-container-low hover:bg-surface-container") +
        (disabled ? " cursor-not-allowed opacity-60" : "")
      }
    >
      {badge && (
        <span className="absolute right-3 top-3 rounded-full bg-surface-container-highest px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          {badge}
        </span>
      )}
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-container-highest text-primary">
        {icon}
      </div>
      <h3 className="mt-1 font-display text-lg tracking-tight text-on-surface">
        {title}
      </h3>
      <p className="text-sm text-on-surface-dim">{description}</p>
      {selected && (
        <span className="absolute right-3 bottom-3 text-primary">✓</span>
      )}
    </button>
  );
}
