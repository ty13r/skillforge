import { useEffect, useRef, useState } from "react";

interface Step {
  number: number;
  title: string;
  description: string;
  metric: string;
  isLoop?: boolean;
  visual: () => JSX.Element;
}

/* ── Mini-visualizations per step ─────────────────────────────────── */

/** Step 1: network graph of ecosystem nodes */
function VisualResearch() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* nodes */}
      {[
        [20, 40], [45, 15], [45, 65], [70, 30], [70, 55],
        [95, 20], [95, 45], [95, 70],
      ].map(([cx, cy], i) => (
        <g key={i}>
          <circle cx={cx} cy={cy} r={i < 3 ? 6 : 4} fill="currentColor"
            className={i < 3 ? "text-tertiary/60" : "text-on-surface-dim/30"} />
        </g>
      ))}
      {/* edges */}
      {[
        [20, 40, 45, 15], [20, 40, 45, 65], [45, 15, 70, 30],
        [45, 65, 70, 55], [70, 30, 95, 20], [70, 30, 95, 45],
        [70, 55, 95, 45], [70, 55, 95, 70],
      ].map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
          stroke="currentColor" strokeWidth="1" className="text-outline-variant" />
      ))}
    </svg>
  );
}

/** Step 2: ranked bars with top 7 highlighted */
function VisualSelect() {
  const heights = [95, 82, 78, 72, 68, 60, 55, 45, 38, 30];
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {heights.map((h, i) => (
        <rect key={i} x={6 + i * 12} y={80 - h * 0.75} width={8} height={h * 0.75}
          rx={2} fill="currentColor"
          className={i < 7 ? "text-tertiary/50" : "text-on-surface-dim/20"} />
      ))}
      <line x1={6 + 7 * 12 - 2} y1={4} x2={6 + 7 * 12 - 2} y2={76}
        stroke="currentColor" strokeWidth="1" strokeDasharray="3,3"
        className="text-tertiary/40" />
    </svg>
  );
}

/** Step 3: tree decomposition */
function VisualDecompose() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      <rect x={45} y={4} width={30} height={14} rx={3}
        fill="currentColor" className="text-tertiary/50" />
      {[20, 50, 80].map((x, i) => (
        <g key={i}>
          <line x1={60} y1={18} x2={x} y2={36}
            stroke="currentColor" strokeWidth="1" className="text-outline-variant" />
          <rect x={x - 12} y={36} width={24} height={10} rx={2}
            fill="currentColor" className="text-primary/30" />
          {[x - 8, x, x + 8].map((cx, j) => (
            <g key={j}>
              <line x1={x} y1={46} x2={cx} y2={60}
                stroke="currentColor" strokeWidth="0.75" className="text-outline-variant" />
              <circle cx={cx} cy={63} r={3} fill="currentColor"
                className="text-on-surface-dim/30" />
            </g>
          ))}
        </g>
      ))}
    </svg>
  );
}

/** Step 4: tiered challenge grid */
function VisualChallenges() {
  const tiers = [
    { y: 8, count: 8, color: "text-green-400/40" },
    { y: 24, count: 6, color: "text-yellow-400/40" },
    { y: 40, count: 4, color: "text-orange-400/40" },
    { y: 56, count: 2, color: "text-red-400/40" },
  ];
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {tiers.map((tier, ti) =>
        Array.from({ length: tier.count }).map((_, i) => (
          <rect key={`${ti}-${i}`} x={8 + i * 14} y={tier.y} width={10} height={10}
            rx={2} fill="currentColor" className={tier.color} />
        )),
      )}
      {["E", "M", "H", "L"].map((label, i) => (
        <text key={label} x={116} y={tiers[i].y + 9}
          className="fill-on-surface-dim/40" fontSize="7" textAnchor="end"
          fontFamily="monospace">{label}</text>
      ))}
    </svg>
  );
}

/** Step 5: score bar dropping */
function VisualBaseline() {
  const bars = [
    { label: "L0", w: 93, color: "text-primary/40" },
    { label: "+C", w: 54, color: "text-tertiary/50" },
    { label: "=F", w: 51, color: "text-on-surface-dim/30" },
  ];
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {bars.map((bar, i) => (
        <g key={bar.label}>
          <text x={4} y={18 + i * 26} className="fill-on-surface-dim/50"
            fontSize="8" fontFamily="monospace">{bar.label}</text>
          <rect x={22} y={10 + i * 26} width={bar.w * 0.9} height={14}
            rx={3} fill="currentColor" className={bar.color} />
          <text x={22 + bar.w * 0.9 + 4} y={21 + i * 26}
            className="fill-on-surface-dim/50" fontSize="7" fontFamily="monospace">
            {bar.w}%
          </text>
        </g>
      ))}
    </svg>
  );
}

/** Step 6: file tree */
function VisualSeed() {
  const files = [
    { indent: 0, name: "SKILL.md", accent: true },
    { indent: 0, name: "scripts/", accent: false },
    { indent: 1, name: "validate.sh", accent: false },
    { indent: 1, name: "helper.py", accent: false },
    { indent: 0, name: "references/", accent: false },
    { indent: 1, name: "guide.md", accent: false },
  ];
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {files.map((f, i) => (
        <g key={i}>
          <rect x={8 + f.indent * 12} y={4 + i * 12} width={f.accent ? 70 : 60}
            height={9} rx={2} fill="currentColor"
            className={f.accent ? "text-tertiary/30" : "text-on-surface-dim/15"} />
          <text x={12 + f.indent * 12} y={11 + i * 12}
            className={f.accent ? "fill-tertiary/70" : "fill-on-surface-dim/50"}
            fontSize="6" fontFamily="monospace">{f.name}</text>
        </g>
      ))}
    </svg>
  );
}

/** Step 7: branching variants */
function VisualSpawn() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* center seed */}
      <circle cx={20} cy={40} r={8} fill="currentColor" className="text-tertiary/40" />
      <text x={20} y={43} textAnchor="middle" className="fill-tertiary/80"
        fontSize="7" fontFamily="monospace">S</text>
      {/* branch lines + variant dots */}
      {[15, 30, 45, 60].map((y, i) => (
        <g key={i}>
          <path d={`M28,40 Q50,40 60,${y}`} fill="none" stroke="currentColor"
            strokeWidth="1" className="text-outline-variant" />
          <circle cx={70} cy={y} r={5} fill="currentColor" className="text-primary/30" />
          <circle cx={90} cy={y} r={5} fill="currentColor" className="text-primary/30" />
          <line x1={75} y1={y} x2={85} y2={y} stroke="currentColor"
            strokeWidth="0.75" className="text-outline-variant" />
        </g>
      ))}
    </svg>
  );
}

/** Step 8: versus matchup */
function VisualCompete() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* left variant */}
      <rect x={8} y={12} width={36} height={56} rx={4}
        fill="currentColor" className="text-primary/15" />
      <text x={26} y={44} textAnchor="middle" className="fill-primary/50"
        fontSize="8" fontFamily="monospace">V1</text>
      {/* VS */}
      <text x={60} y={46} textAnchor="middle" className="fill-on-surface-dim/40"
        fontSize="12" fontWeight="bold">vs</text>
      {/* right variant */}
      <rect x={76} y={12} width={36} height={56} rx={4}
        fill="currentColor" className="text-tertiary/15" />
      <text x={94} y={44} textAnchor="middle" className="fill-tertiary/50"
        fontSize="8" fontFamily="monospace">V2</text>
      {/* challenge dots */}
      {[28, 40, 52].map((y, i) => (
        <g key={i}>
          <circle cx={26} cy={y + 10} r={2} fill="currentColor" className="text-primary/40" />
          <circle cx={94} cy={y + 10} r={2} fill="currentColor" className="text-tertiary/40" />
        </g>
      ))}
    </svg>
  );
}

/** Step 9: scoring layers stacked */
function VisualScore() {
  const layers = [
    { label: "L0", w: 85, color: "text-on-surface-dim/20" },
    { label: "CC", w: 70, color: "text-on-surface-dim/25" },
    { label: "AST", w: 55, color: "text-primary/25" },
    { label: "BEH", w: 90, color: "text-tertiary/40" },
  ];
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {layers.map((l, i) => (
        <g key={l.label}>
          <rect x={20} y={6 + i * 18} width={l.w} height={13} rx={2}
            fill="currentColor" className={l.color} />
          <text x={14} y={15 + i * 18} textAnchor="end"
            className="fill-on-surface-dim/50" fontSize="6" fontFamily="monospace">
            {l.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

/** Step 10: selection funnel */
function VisualBreed() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* population dots top */}
      {[20, 35, 50, 65, 80, 95].map((x, i) => (
        <circle key={`top-${i}`} cx={x} cy={12} r={4} fill="currentColor"
          className={i < 3 ? "text-tertiary/50" : "text-on-surface-dim/20"} />
      ))}
      {/* funnel lines */}
      <path d="M10,24 L50,50 L10,76" fill="currentColor" className="text-tertiary/8"
        stroke="currentColor" strokeWidth="1" />
      <path d="M110,24 L70,50 L110,76" fill="currentColor" className="text-tertiary/8"
        stroke="currentColor" strokeWidth="1" />
      {/* winners bottom */}
      {[35, 55, 75].map((x, i) => (
        <circle key={`bot-${i}`} cx={x} cy={68} r={5} fill="currentColor"
          className="text-tertiary/50" />
      ))}
      {/* arrows */}
      <path d="M60,26 L60,58" stroke="currentColor" strokeWidth="1.5"
        className="text-tertiary/40" markerEnd="url(#arrow)" />
      <defs>
        <marker id="arrow" viewBox="0 0 6 6" refX="3" refY="3"
          markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="currentColor" className="text-tertiary/60" />
        </marker>
      </defs>
    </svg>
  );
}

/** Step 11: merging pieces */
function VisualAssemble() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* incoming pieces */}
      {[
        [10, 10], [10, 30], [10, 50], [10, 70],
        [35, 10], [35, 30], [35, 50], [35, 70],
      ].map(([x, y], i) => (
        <g key={i}>
          <rect x={x} y={y} width={18} height={8} rx={2}
            fill="currentColor" className="text-primary/25" />
          <line x1={x + 18} y1={y + 4} x2={68} y2={40}
            stroke="currentColor" strokeWidth="0.5" className="text-outline-variant" />
        </g>
      ))}
      {/* composite result */}
      <rect x={68} y={20} width={44} height={40} rx={6}
        fill="currentColor" className="text-tertiary/20"
        stroke="currentColor" strokeWidth="1.5" />
      <text x={90} y={44} textAnchor="middle" className="fill-tertiary/60"
        fontSize="7" fontFamily="monospace">SKILL</text>
      <text x={90} y={36} textAnchor="middle" className="fill-tertiary/40"
        fontSize="5" fontFamily="monospace">.md</text>
    </svg>
  );
}

/** Step 12: launch / ship */
function VisualShip() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* checkmarks */}
      {Array.from({ length: 7 }).map((_, i) => (
        <g key={i}>
          <circle cx={16 + i * 15} cy={20} r={6} fill="currentColor"
            className="text-tertiary/30" />
          <path d={`M${12 + i * 15},20 L${15 + i * 15},23 L${20 + i * 15},17`}
            fill="none" stroke="currentColor" strokeWidth="1.5"
            className="text-tertiary/70" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      ))}
      {/* arrow up */}
      <path d="M60,36 L60,70" stroke="currentColor" strokeWidth="2"
        className="text-tertiary/30" />
      <polygon points="52,42 60,32 68,42" fill="currentColor"
        className="text-tertiary/40" />
      {/* Registry label */}
      <rect x={30} y={58} width={60} height={16} rx={4}
        fill="currentColor" className="text-tertiary/15" />
      <text x={60} y={69} textAnchor="middle" className="fill-tertiary/50"
        fontSize="7" fontFamily="monospace">Registry</text>
    </svg>
  );
}

const STEPS: Step[] = [
  {
    number: 1,
    title: "Research Domain",
    description: "Analyze the target ecosystem for skill families worth evolving",
    metric: "34 candidates identified",
    visual: VisualResearch,
  },
  {
    number: 2,
    title: "Select Lighthouse Families",
    description: "Rank by community impact, complexity, and LLM failure rate",
    metric: "7 families selected",
    visual: VisualSelect,
  },
  {
    number: 3,
    title: "Decompose into Capabilities",
    description: "Break each skill into atomic, independently-evolvable dimensions",
    metric: "83 dimensions total",
    visual: VisualDecompose,
  },
  {
    number: 4,
    title: "Generate SKLD-bench Challenges",
    description: "Author challenges per tier: easy, medium, hard, legendary",
    metric: "867 challenges authored",
    visual: VisualChallenges,
  },
  {
    number: 5,
    title: "Run Baselines",
    description: "Score raw Sonnet with no skill guidance to establish the floor",
    metric: "93.3% L0, 51.1% composite",
    visual: VisualBaseline,
  },
  {
    number: 6,
    title: "Research & Create Seed Skill",
    description: "Build a golden-template package: SKILL.md + scripts + references",
    metric: "7 seed packages",
    visual: VisualSeed,
  },
  {
    number: 7,
    title: "Spawn Variants",
    description: "Generate diverse alternatives per dimension",
    metric: "2 variants x 12 dimensions",
    isLoop: true,
    visual: VisualSpawn,
  },
  {
    number: 8,
    title: "Compete",
    description: "Run both variants against sampled challenges from the bench",
    metric: "4 dispatches per dimension",
    isLoop: true,
    visual: VisualCompete,
  },
  {
    number: 9,
    title: "Score",
    description: "L0 string match + Compile + AST + Behavioral = composite fitness",
    metric: "6-layer composite scorer",
    isLoop: true,
    visual: VisualScore,
  },
  {
    number: 10,
    title: "Judge & Breed",
    description: "Pick winners, mutate losers based on execution traces",
    metric: "Repeat N generations",
    isLoop: true,
    visual: VisualBreed,
  },
  {
    number: 11,
    title: "Assemble Composite",
    description: "Merge winning variants from all dimensions into one skill",
    metric: "1 composite package",
    visual: VisualAssemble,
  },
  {
    number: 12,
    title: "Ship",
    description: "Install test, extract findings to the Bible, publish to Registry",
    metric: "7/7 positive skill lift",
    visual: VisualShip,
  },
];

/**
 * Animated process flow showing the 12 steps of the SKLD pipeline.
 * Steps appear as the user scrolls down using Intersection Observer.
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
        <p className="font-mono text-xs uppercase tracking-wider text-tertiary">
          How SKLD Works
        </p>
        <h2 className="mt-2 font-display text-4xl tracking-tight md:text-5xl">
          The Evolution Pipeline
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-base text-on-surface-dim">
          From ecosystem research to a shipped, tested skill package — every
          step backed by measured data from real experiments.
        </p>
      </div>

      <div className="relative mx-auto max-w-4xl">
        {/* Vertical line */}
        <div className="absolute left-8 top-0 bottom-0 w-px bg-outline-variant md:left-1/2" />

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
                isVisible
                  ? "translate-y-0 opacity-100"
                  : "translate-y-8 opacity-0"
              }`}
            >
              {/* Timeline dot */}
              <div
                className={`absolute left-8 z-10 -translate-x-1/2 md:left-1/2 ${
                  step.isLoop
                    ? "h-5 w-5 rounded-full border-2 border-tertiary bg-surface-container-lowest"
                    : "h-5 w-5 rounded-full bg-tertiary"
                }`}
                style={{ top: "1.5rem" }}
              />

              {/* Content card */}
              <div
                className={`ml-16 md:ml-0 ${
                  isRight
                    ? "md:ml-[calc(50%+2rem)]"
                    : "md:mr-[calc(50%+2rem)]"
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
                        <h3 className="font-display text-lg tracking-tight">
                          {step.title}
                        </h3>
                        {step.isLoop && (
                          <span className="rounded bg-tertiary/15 px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
                            loop
                          </span>
                        )}
                      </div>
                      <p className="mt-1.5 text-sm text-on-surface-dim">
                        {step.description}
                      </p>
                      <p className="mt-2 font-mono text-xs text-tertiary">
                        {step.metric}
                      </p>
                    </div>
                    {/* Visual illustration */}
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
