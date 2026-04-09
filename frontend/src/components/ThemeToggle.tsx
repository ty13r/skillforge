import { useTheme, type Theme } from "../hooks/useTheme";

const OPTIONS: { value: Theme; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "☀" },
  { value: "system", label: "System", icon: "🖥" },
  { value: "dark", label: "Dark", icon: "🌙" },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-0.5 rounded-xl border border-outline-variant bg-surface-container-low p-0.5">
      {OPTIONS.map((opt) => {
        const selected = theme === opt.value;
        return (
          <button
            key={opt.value}
            onClick={() => setTheme(opt.value)}
            title={opt.label}
            aria-label={opt.label}
            aria-pressed={selected}
            className={
              "flex h-7 w-7 items-center justify-center rounded-lg text-xs transition-colors " +
              (selected
                ? "bg-primary/15 text-primary"
                : "text-on-surface-dim hover:text-on-surface")
            }
          >
            <span aria-hidden>{opt.icon}</span>
          </button>
        );
      })}
    </div>
  );
}
