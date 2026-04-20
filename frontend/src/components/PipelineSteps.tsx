import { useEffect, useRef, useState } from "react";

import { STEPS } from "./pipelineSteps/steps";

/**
 * Animated process flow showing the 12 steps of the SKLD pipeline.
 * Each step fades in as the user scrolls to it via IntersectionObserver.
 *
 * The 12 SVG illustrations live in ``pipelineSteps/foundationVisuals``
 * (steps 1-6, one-shot setup) and ``pipelineSteps/loopVisuals`` (steps
 * 7-12, the evolution loop + shipping). Step metadata + ordering lives
 * in ``pipelineSteps/steps.ts``. This file is the observer + layout.
 */
export default function PipelineSteps() {
  const [visibleSteps, setVisibleSteps] = useState<Set<number>>(new Set());
  const stepsRef = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const idx = Number(entry.target.getAttribute("data-step-idx"));
            if (!isNaN(idx)) {
              setVisibleSteps((prev) => new Set(prev).add(idx));
            }
          }
        });
      },
      { threshold: 0.3, rootMargin: "0px 0px -50px 0px" },
    );

    stepsRef.current.forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <section className="mt-16">
      <div className="mb-12 text-center">
        <p className="font-mono text-xs uppercase tracking-wider text-tertiary">How SKLD Works</p>
        <h2 className="mt-2 font-display text-4xl tracking-tight md:text-5xl">
          The Evolution Pipeline
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-base text-on-surface-dim">
          From ecosystem research to a shipped, tested skill package — every step backed by measured
          data from real experiments.
        </p>
      </div>

      <div className="relative mx-auto max-w-4xl">
        {/* Vertical line */}
        <div className="absolute bottom-0 left-8 top-0 w-px bg-outline-variant md:left-1/2" />

        {STEPS.map((step, i) => {
          const isVisible = visibleSteps.has(i);
          const isRight = i % 2 === 1;
          const Visual = step.visual;

          return (
            <div
              key={step.number}
              ref={(el) => {
                stepsRef.current[i] = el;
              }}
              data-step-idx={i}
              className={`relative mb-10 transition-all duration-700 ease-out ${
                isVisible ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
              }`}
            >
              <div
                className={`absolute left-8 z-10 -translate-x-1/2 md:left-1/2 ${
                  step.isLoop
                    ? "h-5 w-5 rounded-full border-2 border-tertiary bg-surface-container-lowest"
                    : "h-5 w-5 rounded-full bg-tertiary"
                }`}
                style={{ top: "1.5rem" }}
              />

              <div
                className={`ml-16 md:ml-0 ${
                  isRight ? "md:ml-[calc(50%+2rem)]" : "md:mr-[calc(50%+2rem)]"
                }`}
              >
                <div
                  className={`rounded-xl border p-5 transition-colors ${
                    step.isLoop
                      ? "border-tertiary/30 bg-tertiary/5"
                      : "border-outline-variant bg-surface-container-lowest"
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono text-xs text-on-surface-dim">
                          {String(step.number).padStart(2, "0")}
                        </span>
                        <h3 className="font-display text-lg tracking-tight">{step.title}</h3>
                        {step.isLoop && (
                          <span className="rounded bg-tertiary/15 px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
                            loop
                          </span>
                        )}
                      </div>
                      <p className="mt-1.5 text-sm text-on-surface-dim">{step.description}</p>
                      <p className="mt-2 font-mono text-xs text-tertiary">{step.metric}</p>
                    </div>
                    <div className="hidden h-20 w-32 shrink-0 sm:block">
                      <Visual />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
