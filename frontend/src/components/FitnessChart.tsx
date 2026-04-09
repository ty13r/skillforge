import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCssVar } from "../hooks/useCssVar";
import type { GenerationStats } from "../types";

interface FitnessChartProps {
  generations: GenerationStats[];
}

export default function FitnessChart({ generations }: FitnessChartProps) {
  const primary = useCssVar("--color-primary");
  const tertiary = useCssVar("--color-tertiary");
  const gridColor = useCssVar("--color-on-surface", 0.06);
  const axisColor = useCssVar("--color-on-surface-dim");
  const tooltipBg = useCssVar("--color-surface-mid");
  const tooltipBorder = useCssVar("--color-outline-variant");

  const data = generations.map((g) => ({
    gen: `Gen ${g.number}`,
    best: g.best_fitness ?? 0,
    avg: g.avg_fitness ?? 0,
  }));

  if (data.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-xs text-on-surface-dim">
        No fitness data yet.
      </div>
    );
  }

  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
          <CartesianGrid stroke={gridColor} />
          <XAxis dataKey="gen" stroke={axisColor} fontSize={11} />
          <YAxis stroke={axisColor} fontSize={11} domain={[0, 1]} />
          <Tooltip
            contentStyle={{
              background: tooltipBg,
              border: `1px solid ${tooltipBorder}`,
              borderRadius: "8px",
              fontFamily: "JetBrains Mono",
              fontSize: "11px",
            }}
          />
          <Line
            type="monotone"
            dataKey="best"
            stroke={primary}
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="avg"
            stroke={tertiary}
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
