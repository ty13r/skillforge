import { useEffect, useRef } from "react";

import type { EvolutionEvent } from "../types";

interface LiveFeedLogProps {
  events: EvolutionEvent[];
}

const ACTOR_COLOR: Record<string, string> = {
  run_started: "text-primary",
  challenge_designed: "text-secondary",
  generation_started: "text-secondary",
  competitor_started: "text-on-surface",
  competitor_finished: "text-tertiary",
  judging_started: "text-warning",
  scores_published: "text-tertiary",
  cost_update: "text-on-surface-dim",
  breeding_started: "text-primary",
  breeding_report: "text-primary",
  generation_complete: "text-tertiary",
  evolution_complete: "text-tertiary",
  run_failed: "text-error",
};

const ACTOR_BAR_BG: Record<string, string> = {
  run_started: "bg-primary",
  challenge_designed: "bg-secondary",
  generation_started: "bg-secondary",
  competitor_started: "bg-on-surface",
  competitor_finished: "bg-tertiary",
  judging_started: "bg-warning",
  scores_published: "bg-tertiary",
  cost_update: "bg-on-surface-dim",
  breeding_started: "bg-primary",
  breeding_report: "bg-primary",
  generation_complete: "bg-tertiary",
  evolution_complete: "bg-tertiary",
  run_failed: "bg-error",
};

function formatEvent(ev: EvolutionEvent): string {
  switch (ev.event) {
    case "run_started":
      return `Run started: ${ev.specialization?.slice(0, 60) ?? ""}`;
    case "challenge_designed":
      return `Challenge ${ev.challenge_id?.slice(0, 8)} (${ev.difficulty}): ${ev.prompt?.slice(0, 60) ?? ""}`;
    case "generation_started":
      return `Generation ${ev.generation} started`;
    case "competitor_started":
      return `Competitor ${ev.competitor} (skill ${ev.skill_id?.slice(0, 8)}) started`;
    case "competitor_finished":
      return `Competitor ${ev.competitor} finished — trace length ${ev.trace_length}`;
    case "judging_started":
      return `Judging pipeline started for generation ${ev.generation}`;
    case "scores_published":
      return `Scores: best=${ev.best_fitness?.toFixed(3)} avg=${ev.avg_fitness?.toFixed(3)} pareto=${ev.pareto_front?.length ?? 0}`;
    case "cost_update":
      return `Cost: $${ev.generation_cost_usd?.toFixed(4)} this gen / $${ev.total_cost_usd?.toFixed(4)} total`;
    case "breeding_started":
      return `Breeding next generation...`;
    case "breeding_report":
      return `Breeding report ready (${ev.new_lessons?.length ?? 0} new lessons)`;
    case "generation_complete":
      return `Generation ${ev.generation} complete`;
    case "evolution_complete":
      return `EVOLUTION COMPLETE — best skill ${ev.best_skill_id?.slice(0, 8) ?? "—"}, $${ev.total_cost_usd?.toFixed(4)} spent`;
    case "run_failed":
      return `RUN FAILED: ${ev.reason ?? "(no reason)"}`;
    default:
      return ev.event;
  }
}

function timestamp(): string {
  const d = new Date();
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}

export default function LiveFeedLog({ events }: LiveFeedLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const errorCount = events.filter((e) => e.event === "run_failed").length;

  return (
    <div className="rounded-xl bg-surface-container-lowest">
      <div className="flex items-center justify-between px-4 py-2">
        <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Live Feed Log
        </span>
        <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          {errorCount} Errors
        </span>
      </div>
      <div ref={scrollRef} className="max-h-64 overflow-y-auto px-4 pb-3 font-mono text-xs">
        {events.length === 0 ? (
          <p className="py-2 text-on-surface-dim">
            <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-secondary align-middle" />
            Waiting for events from the engine...
          </p>
        ) : (
          events.map((ev, i) => (
            <div key={i} className="flex animate-slide-in-up items-start gap-2 py-0.5">
              <span
                className={
                  "mt-[0.4rem] inline-block h-1 w-1 shrink-0 rounded-full " +
                  (ACTOR_BAR_BG[ev.event] ?? "bg-on-surface-dim")
                }
                aria-hidden="true"
              />
              <span className="text-on-surface-dim">[{timestamp()}]</span>
              <span className={ACTOR_COLOR[ev.event] ?? "text-on-surface"}>
                {ev.event.toUpperCase()}:
              </span>
              <span className="min-w-0 flex-1 break-words text-on-surface">{formatEvent(ev)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
