/** Radio-style picker for the three Starting Point options. */
import type { SourceMode } from "./types";

interface Option {
  value: SourceMode;
  label: string;
  hint: string;
}

const OPTIONS: Option[] = [
  {
    value: "scratch",
    label: "From Scratch",
    hint: "Describe a domain and evolve a new Skill from the golden template.",
  },
  {
    value: "upload",
    label: "Upload Existing",
    hint: "Bring your own SKILL.md (or zipped Skill dir) and evolve it forward.",
  },
  {
    value: "fork",
    label: "Fork from Registry",
    hint: "Pick a curated Gen 0 Skill from the library as your starting point.",
  },
];

interface SourceModePickerProps {
  value: SourceMode;
  onChange: (next: SourceMode) => void;
}

export default function SourceModePicker({ value, onChange }: SourceModePickerProps) {
  return (
    <div>
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Starting Point
      </p>
      <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
        {OPTIONS.map((m) => {
          const selected = value === m.value;
          return (
            <button
              key={m.value}
              onClick={() => onChange(m.value)}
              className={`rounded-xl border p-4 text-left transition-all ${
                selected
                  ? "border-primary bg-primary/5 ring-1 ring-primary/40"
                  : "border-outline-variant bg-surface-container-lowest hover:border-primary/40"
              }`}
            >
              <p
                className={`font-display text-sm tracking-tight ${
                  selected ? "text-primary" : "text-on-surface"
                }`}
              >
                {m.label}
              </p>
              <p className="mt-1 text-xs text-on-surface-dim">{m.hint}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
