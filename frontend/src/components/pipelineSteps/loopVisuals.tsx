/** SVG mini-illustrations for pipeline steps 7-12 (spawn → ship).
 *
 * Pure functions — no state, no props. Split from the foundation
 * half at the natural seam between one-shot setup and the evolution
 * loop that runs N generations.
 */
/** Step 7: branching variants */
export function VisualSpawn() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* center seed */}
      <circle cx={20} cy={40} r={8} fill="currentColor" className="text-tertiary/40" />
      <text
        x={20}
        y={43}
        textAnchor="middle"
        className="fill-tertiary/80"
        fontSize="7"
        fontFamily="monospace"
      >
        S
      </text>
      {/* branch lines + variant dots */}
      {[15, 30, 45, 60].map((y, i) => (
        <g key={i}>
          <path
            d={`M28,40 Q50,40 60,${y}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            className="text-outline-variant"
          />
          <circle cx={70} cy={y} r={5} fill="currentColor" className="text-primary/30" />
          <circle cx={90} cy={y} r={5} fill="currentColor" className="text-primary/30" />
          <line
            x1={75}
            y1={y}
            x2={85}
            y2={y}
            stroke="currentColor"
            strokeWidth="0.75"
            className="text-outline-variant"
          />
        </g>
      ))}
    </svg>
  );
}

/** Step 8: versus matchup */
export function VisualCompete() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* left variant */}
      <rect
        x={8}
        y={12}
        width={36}
        height={56}
        rx={4}
        fill="currentColor"
        className="text-primary/15"
      />
      <text
        x={26}
        y={44}
        textAnchor="middle"
        className="fill-primary/50"
        fontSize="8"
        fontFamily="monospace"
      >
        V1
      </text>
      {/* VS */}
      <text
        x={60}
        y={46}
        textAnchor="middle"
        className="fill-on-surface-dim/40"
        fontSize="12"
        fontWeight="bold"
      >
        vs
      </text>
      {/* right variant */}
      <rect
        x={76}
        y={12}
        width={36}
        height={56}
        rx={4}
        fill="currentColor"
        className="text-tertiary/15"
      />
      <text
        x={94}
        y={44}
        textAnchor="middle"
        className="fill-tertiary/50"
        fontSize="8"
        fontFamily="monospace"
      >
        V2
      </text>
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
export function VisualScore() {
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
          <rect
            x={20}
            y={6 + i * 18}
            width={l.w}
            height={13}
            rx={2}
            fill="currentColor"
            className={l.color}
          />
          <text
            x={14}
            y={15 + i * 18}
            textAnchor="end"
            className="fill-on-surface-dim/50"
            fontSize="6"
            fontFamily="monospace"
          >
            {l.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

/** Step 10: selection funnel */
export function VisualBreed() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* population dots top */}
      {[20, 35, 50, 65, 80, 95].map((x, i) => (
        <circle
          key={`top-${i}`}
          cx={x}
          cy={12}
          r={4}
          fill="currentColor"
          className={i < 3 ? "text-tertiary/50" : "text-on-surface-dim/20"}
        />
      ))}
      {/* funnel lines */}
      <path
        d="M10,24 L50,50 L10,76"
        fill="currentColor"
        className="text-tertiary/8"
        stroke="currentColor"
        strokeWidth="1"
      />
      <path
        d="M110,24 L70,50 L110,76"
        fill="currentColor"
        className="text-tertiary/8"
        stroke="currentColor"
        strokeWidth="1"
      />
      {/* winners bottom */}
      {[35, 55, 75].map((x, i) => (
        <circle
          key={`bot-${i}`}
          cx={x}
          cy={68}
          r={5}
          fill="currentColor"
          className="text-tertiary/50"
        />
      ))}
      {/* arrows */}
      <path
        d="M60,26 L60,58"
        stroke="currentColor"
        strokeWidth="1.5"
        className="text-tertiary/40"
        markerEnd="url(#arrow)"
      />
      <defs>
        <marker
          id="arrow"
          viewBox="0 0 6 6"
          refX="3"
          refY="3"
          markerWidth="4"
          markerHeight="4"
          orient="auto"
        >
          <path d="M0,0 L6,3 L0,6 Z" fill="currentColor" className="text-tertiary/60" />
        </marker>
      </defs>
    </svg>
  );
}

/** Step 11: merging pieces */
export function VisualAssemble() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* incoming pieces */}
      {[
        [10, 10],
        [10, 30],
        [10, 50],
        [10, 70],
        [35, 10],
        [35, 30],
        [35, 50],
        [35, 70],
      ].map(([x, y], i) => (
        <g key={i}>
          <rect
            x={x}
            y={y}
            width={18}
            height={8}
            rx={2}
            fill="currentColor"
            className="text-primary/25"
          />
          <line
            x1={x + 18}
            y1={y + 4}
            x2={68}
            y2={40}
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-outline-variant"
          />
        </g>
      ))}
      {/* composite result */}
      <rect
        x={68}
        y={20}
        width={44}
        height={40}
        rx={6}
        fill="currentColor"
        className="text-tertiary/20"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <text
        x={90}
        y={44}
        textAnchor="middle"
        className="fill-tertiary/60"
        fontSize="7"
        fontFamily="monospace"
      >
        SKILL
      </text>
      <text
        x={90}
        y={36}
        textAnchor="middle"
        className="fill-tertiary/40"
        fontSize="5"
        fontFamily="monospace"
      >
        .md
      </text>
    </svg>
  );
}

/** Step 12: launch / ship */
export function VisualShip() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* checkmarks */}
      {Array.from({ length: 7 }).map((_, i) => (
        <g key={i}>
          <circle cx={16 + i * 15} cy={20} r={6} fill="currentColor" className="text-tertiary/30" />
          <path
            d={`M${12 + i * 15},20 L${15 + i * 15},23 L${20 + i * 15},17`}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="text-tertiary/70"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
      ))}
      {/* arrow up */}
      <path d="M60,36 L60,70" stroke="currentColor" strokeWidth="2" className="text-tertiary/30" />
      <polygon points="52,42 60,32 68,42" fill="currentColor" className="text-tertiary/40" />
      {/* Registry label */}
      <rect
        x={30}
        y={58}
        width={60}
        height={16}
        rx={4}
        fill="currentColor"
        className="text-tertiary/15"
      />
      <text
        x={60}
        y={69}
        textAnchor="middle"
        className="fill-tertiary/50"
        fontSize="7"
        fontFamily="monospace"
      >
        Registry
      </text>
    </svg>
  );
}
