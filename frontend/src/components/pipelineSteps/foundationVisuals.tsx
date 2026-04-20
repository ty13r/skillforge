/** SVG mini-illustrations for pipeline steps 1-6 (research → seed).
 *
 * All pure functions — no state, no props. Extracted from PipelineSteps
 * so the main component stays focused on observer wiring + layout.
 */

/** Step 1: network graph of ecosystem nodes */
export function VisualResearch() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {/* nodes */}
      {[
        [20, 40],
        [45, 15],
        [45, 65],
        [70, 30],
        [70, 55],
        [95, 20],
        [95, 45],
        [95, 70],
      ].map(([cx, cy], i) => (
        <g key={i}>
          <circle
            cx={cx}
            cy={cy}
            r={i < 3 ? 6 : 4}
            fill="currentColor"
            className={i < 3 ? "text-tertiary/60" : "text-on-surface-dim/30"}
          />
        </g>
      ))}
      {/* edges */}
      {[
        [20, 40, 45, 15],
        [20, 40, 45, 65],
        [45, 15, 70, 30],
        [45, 65, 70, 55],
        [70, 30, 95, 20],
        [70, 30, 95, 45],
        [70, 55, 95, 45],
        [70, 55, 95, 70],
      ].map(([x1, y1, x2, y2], i) => (
        <line
          key={i}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke="currentColor"
          strokeWidth="1"
          className="text-outline-variant"
        />
      ))}
    </svg>
  );
}

/** Step 2: ranked bars with top 7 highlighted */
export function VisualSelect() {
  const heights = [95, 82, 78, 72, 68, 60, 55, 45, 38, 30];
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {heights.map((h, i) => (
        <rect
          key={i}
          x={6 + i * 12}
          y={80 - h * 0.75}
          width={8}
          height={h * 0.75}
          rx={2}
          fill="currentColor"
          className={i < 7 ? "text-tertiary/50" : "text-on-surface-dim/20"}
        />
      ))}
      <line
        x1={6 + 7 * 12 - 2}
        y1={4}
        x2={6 + 7 * 12 - 2}
        y2={76}
        stroke="currentColor"
        strokeWidth="1"
        strokeDasharray="3,3"
        className="text-tertiary/40"
      />
    </svg>
  );
}

/** Step 3: tree decomposition */
export function VisualDecompose() {
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      <rect
        x={45}
        y={4}
        width={30}
        height={14}
        rx={3}
        fill="currentColor"
        className="text-tertiary/50"
      />
      {[20, 50, 80].map((x, i) => (
        <g key={i}>
          <line
            x1={60}
            y1={18}
            x2={x}
            y2={36}
            stroke="currentColor"
            strokeWidth="1"
            className="text-outline-variant"
          />
          <rect
            x={x - 12}
            y={36}
            width={24}
            height={10}
            rx={2}
            fill="currentColor"
            className="text-primary/30"
          />
          {[x - 8, x, x + 8].map((cx, j) => (
            <g key={j}>
              <line
                x1={x}
                y1={46}
                x2={cx}
                y2={60}
                stroke="currentColor"
                strokeWidth="0.75"
                className="text-outline-variant"
              />
              <circle
                cx={cx}
                cy={63}
                r={3}
                fill="currentColor"
                className="text-on-surface-dim/30"
              />
            </g>
          ))}
        </g>
      ))}
    </svg>
  );
}

/** Step 4: tiered challenge grid */
export function VisualChallenges() {
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
          <rect
            key={`${ti}-${i}`}
            x={8 + i * 14}
            y={tier.y}
            width={10}
            height={10}
            rx={2}
            fill="currentColor"
            className={tier.color}
          />
        )),
      )}
      {["E", "M", "H", "L"].map((label, i) => (
        <text
          key={label}
          x={116}
          y={tiers[i].y + 9}
          className="fill-on-surface-dim/40"
          fontSize="7"
          textAnchor="end"
          fontFamily="monospace"
        >
          {label}
        </text>
      ))}
    </svg>
  );
}

/** Step 5: score bar dropping */
export function VisualBaseline() {
  const bars = [
    { label: "L0", w: 93, color: "text-primary/40" },
    { label: "+C", w: 54, color: "text-tertiary/50" },
    { label: "=F", w: 51, color: "text-on-surface-dim/30" },
  ];
  return (
    <svg viewBox="0 0 120 80" className="h-full w-full">
      {bars.map((bar, i) => (
        <g key={bar.label}>
          <text
            x={4}
            y={18 + i * 26}
            className="fill-on-surface-dim/50"
            fontSize="8"
            fontFamily="monospace"
          >
            {bar.label}
          </text>
          <rect
            x={22}
            y={10 + i * 26}
            width={bar.w * 0.9}
            height={14}
            rx={3}
            fill="currentColor"
            className={bar.color}
          />
          <text
            x={22 + bar.w * 0.9 + 4}
            y={21 + i * 26}
            className="fill-on-surface-dim/50"
            fontSize="7"
            fontFamily="monospace"
          >
            {bar.w}%
          </text>
        </g>
      ))}
    </svg>
  );
}

/** Step 6: file tree */
export function VisualSeed() {
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
          <rect
            x={8 + f.indent * 12}
            y={4 + i * 12}
            width={f.accent ? 70 : 60}
            height={9}
            rx={2}
            fill="currentColor"
            className={f.accent ? "text-tertiary/30" : "text-on-surface-dim/15"}
          />
          <text
            x={12 + f.indent * 12}
            y={11 + i * 12}
            className={f.accent ? "fill-tertiary/70" : "fill-on-surface-dim/50"}
            fontSize="6"
            fontFamily="monospace"
          >
            {f.name}
          </text>
        </g>
      ))}
    </svg>
  );
}
