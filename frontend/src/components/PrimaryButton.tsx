import type { ButtonHTMLAttributes, ReactNode } from "react";

interface PrimaryButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
}

export default function PrimaryButton({
  children,
  className = "",
  ...rest
}: PrimaryButtonProps) {
  return (
    <button
      className={
        "inline-flex items-center gap-2 rounded-xl bg-primary-gradient px-5 py-2.5 " +
        "text-sm font-medium text-surface-container-lowest shadow-elevated " +
        "transition-transform hover:scale-[1.02] active:scale-[0.98] " +
        "disabled:cursor-not-allowed disabled:opacity-50 " +
        className
      }
      {...rest}
    >
      {children}
    </button>
  );
}
