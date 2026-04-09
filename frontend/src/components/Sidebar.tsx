import { Link } from "react-router-dom";

interface SidebarProps {
  runId: string;
  generation: number;
  totalGenerations?: number;
}

export default function Sidebar({
  runId,
  generation,
  totalGenerations,
}: SidebarProps) {
  return (
    <aside className="w-60 shrink-0 bg-surface-container py-6">
      <div className="mx-4 rounded-xl bg-surface-container-low p-4">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Project Evolve
        </p>
        <p className="mt-1 text-sm text-on-surface">
          Active Generation:{" "}
          <span className="font-mono text-primary">{generation}</span>
          {totalGenerations && (
            <span className="text-on-surface-dim"> / {totalGenerations}</span>
          )}
        </p>
        <p className="mt-1 font-mono text-[0.6875rem] text-on-surface-dim">
          {runId.slice(0, 12)}
        </p>
      </div>

      <nav className="mt-6 px-2">
        <SidebarItem label="Evolution Arena" active />
        <SidebarItem label="Breeding Reports" />
        <SidebarItem label="Gen Stats" />
        <SidebarItem label="Learning Log" />
        <SidebarItem label="Terminal" />
      </nav>

      <div className="mt-8 px-4">
        <Link
          to="/new"
          className="block rounded-xl bg-primary-gradient px-4 py-2 text-center text-sm font-medium text-surface-container-lowest"
        >
          + New Experiment
        </Link>
      </div>

      <nav className="mt-6 px-2 text-xs text-on-surface-dim">
        <SidebarItem label="Settings" muted />
        <SidebarItem label="Docs" muted />
      </nav>
    </aside>
  );
}

function SidebarItem({
  label,
  active = false,
  muted = false,
}: {
  label: string;
  active?: boolean;
  muted?: boolean;
}) {
  return (
    <div
      className={
        "rounded-xl px-3 py-2 text-sm transition-colors " +
        (active
          ? "bg-surface-container-high text-on-surface"
          : muted
            ? "text-on-surface-dim hover:bg-surface-container-high"
            : "text-on-surface-dim hover:bg-surface-container-high hover:text-on-surface")
      }
    >
      {label}
    </div>
  );
}
