import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { RunReportSummary } from "../types";

interface RunNarrativeProps {
  learningLog: string[];
  summary: RunReportSummary;
}

const INTEGRATION_REPORT_PREFIX = "[integration_report] ";

/**
 * Renders the post-run narrative for an atomic-mode run.
 *
 * Layout:
 *   1. Summary callout (best skill, aggregate fitness, wall clock, cost).
 *   2. Key discoveries list (from the report summary).
 *   3. Audit timeline: one entry per learning_log line (excluding the
 *      integration report).
 *   4. Integration report (collapsible) — the Engineer's reconstructed
 *      post-assembly narrative with conflicts, resolutions, and decisions.
 */
export default function RunNarrative({
  learningLog,
  summary,
}: RunNarrativeProps) {
  const [showReport, setShowReport] = useState(true);

  const regularEntries = learningLog.filter(
    (e) => !e.startsWith(INTEGRATION_REPORT_PREFIX),
  );
  const integrationReportEntry = learningLog.find((e) =>
    e.startsWith(INTEGRATION_REPORT_PREFIX),
  );
  const integrationReportMd = integrationReportEntry?.slice(
    INTEGRATION_REPORT_PREFIX.length,
  );

  const wallClockMin =
    summary.wall_clock_duration_sec !== null
      ? (summary.wall_clock_duration_sec / 60).toFixed(1)
      : null;

  return (
    <div className="space-y-6">
      {/* Summary callout */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Narrative Summary
        </p>
        <div className="mt-3 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div>
            <p className="font-display text-3xl tracking-tight text-tertiary">
              {summary.aggregate_fitness.toFixed(3)}
            </p>
            <p className="mt-1 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Aggregate Fitness
            </p>
          </div>
          <div>
            <p className="font-display text-3xl tracking-tight">
              {summary.dimensions_evolved.length}
            </p>
            <p className="mt-1 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Dimensions
            </p>
          </div>
          <div>
            <p className="font-display text-3xl tracking-tight">
              ${summary.total_cost_usd.toFixed(2)}
            </p>
            <p className="mt-1 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Total Cost
            </p>
          </div>
          <div>
            <p className="font-display text-3xl tracking-tight">
              {wallClockMin !== null ? `${wallClockMin}m` : "—"}
            </p>
            <p className="mt-1 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Wall Clock
            </p>
          </div>
        </div>
      </div>

      {/* Key discoveries */}
      {summary.key_discoveries.length > 0 && (
        <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Key Discoveries
          </p>
          <ul className="mt-3 space-y-2">
            {summary.key_discoveries.map((discovery, idx) => (
              <li
                key={idx}
                className="rounded-lg bg-surface-container-low p-3 font-mono text-xs text-on-surface"
              >
                <span className="mr-2 text-tertiary">→</span>
                {discovery}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Audit timeline */}
      {regularEntries.length > 0 && (
        <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Audit Timeline
          </p>
          <ol className="mt-3 space-y-2">
            {regularEntries.map((entry, idx) => (
              <li
                key={idx}
                className="flex items-start gap-3 font-mono text-xs text-on-surface-dim"
              >
                <span className="mt-0.5 font-bold text-tertiary">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <span className="flex-1">{entry}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Integration report */}
      {integrationReportMd && (
        <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
          <button
            type="button"
            onClick={() => setShowReport((v) => !v)}
            className="flex w-full items-center justify-between font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim transition-colors hover:text-on-surface"
          >
            <span>Engineer Integration Report</span>
            <span>{showReport ? "▼" : "▶"}</span>
          </button>
          {showReport && (
            <div className="mt-4 bible-prose">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {integrationReportMd}
              </ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
