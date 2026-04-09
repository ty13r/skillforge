import { Link } from "react-router-dom";

import ProcessFlow from "./ProcessFlow";
import type { PhaseState } from "../types";

interface SidebarProps {
  runId: string;
  generation: number;
  totalGenerations?: number;
  phases: PhaseState[];
}

export default function Sidebar({
  runId,
  generation,
  totalGenerations,
  phases,
}: SidebarProps) {
  return (
    <aside className="w-64 shrink-0 bg-surface-container py-6">
      {/* Project header */}
      <div className="mx-4 rounded-xl bg-surface-container-low p-4">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Active Run
        </p>
        <p className="mt-1 font-mono text-[0.6875rem] text-on-surface-dim">
          {runId.slice(0, 12)}
        </p>
      </div>

      {/* Process flow diagram */}
      <div className="mx-2 mt-6">
        <ProcessFlow
          phases={phases}
          currentGeneration={generation}
          totalGenerations={totalGenerations}
        />
      </div>

      {/* Bottom actions */}
      <div className="mt-8 px-4">
        <Link
          to="/new"
          className="block rounded-xl bg-primary-gradient px-4 py-2 text-center text-sm font-medium text-surface-container-lowest transition-transform hover:scale-[1.02]"
        >
          + New Experiment
        </Link>
      </div>
    </aside>
  );
}
