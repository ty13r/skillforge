import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { GenerationStats } from "../types";

interface FitnessChartProps {
  generations: GenerationStats[];
}

export default function FitnessChart({ generations }: FitnessChartProps) {
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
          <CartesianGrid stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="gen" stroke="#9ba0b8" fontSize={11} />
          <YAxis stroke="#9ba0b8" fontSize={11} domain={[0, 1]} />
          <Tooltip
            contentStyle={{
              background: "#1b1f2c",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "12px",
              fontFamily: "JetBrains Mono",
              fontSize: "11px",
            }}
          />
          <Line
            type="monotone"
            dataKey="best"
            stroke="#c0c1ff"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="avg"
            stroke="#5de6ff"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
