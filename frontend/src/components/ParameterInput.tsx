import type { ChangeEvent } from "react";

interface ParameterInputProps {
  label: string;
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
  prefix?: string;
  accent?: "primary" | "tertiary";
}

export default function ParameterInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
  prefix,
  accent = "primary",
}: ParameterInputProps) {
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const next = Number(e.target.value);
    if (!Number.isNaN(next)) onChange(next);
  };

  const accentClass = accent === "tertiary" ? "text-tertiary" : "text-on-surface";

  return (
    <div className="rounded-xl bg-surface-container-low p-4">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        {label}
      </p>
      <div className="mt-2 flex items-baseline gap-1">
        {prefix && <span className={"font-display text-2xl " + accentClass}>{prefix}</span>}
        <input
          type="number"
          value={value}
          onChange={handleChange}
          min={min}
          max={max}
          step={step}
          className={
            "w-full bg-transparent font-display text-2xl tracking-tight outline-none " + accentClass
          }
        />
      </div>
    </div>
  );
}
