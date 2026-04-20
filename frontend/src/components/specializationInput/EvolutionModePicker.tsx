/** Radio-style picker for Auto / Atomic / Classic evolution modes. */
import type { EvolutionMode } from "./types";

const OPTIONS: { value: EvolutionMode; label: string; hint: string }[] = [
  {
    value: "auto",
    label: "Auto",
    hint: "Taxonomist picks atomic vs molecular per spec",
  },
  {
    value: "atomic",
    label: "Atomic",
    hint: "Decompose into per-dimension variants then assemble",
  },
  {
    value: "molecular",
    label: "Classic",
    hint: "Evolve the whole skill as one unit (v1.x pipeline)",
  },
];

interface EvolutionModePickerProps {
  value: EvolutionMode;
  onChange: (next: EvolutionMode) => void;
}

export default function EvolutionModePicker({ value, onChange }: EvolutionModePickerProps) {
  return (
    <div>
      <p className="mb-2 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Evolution Mode
      </p>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`flex-1 rounded-xl border px-4 py-3 text-left transition-all ${
              value === opt.value
                ? "border-primary bg-primary/10"
                : "border-outline-variant bg-surface-container-lowest hover:border-primary/40"
            }`}
          >
            <div
              className={`font-medium ${value === opt.value ? "text-primary" : "text-on-surface"}`}
            >
              {opt.label}
            </div>
            <div className="mt-1 text-xs text-on-surface-dim">{opt.hint}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
