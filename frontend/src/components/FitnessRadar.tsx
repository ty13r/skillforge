import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";

import { useCssVar } from "../hooks/useCssVar";

interface FitnessRadarProps {
  objectives: Record<string, number>;
}

export default function FitnessRadar({ objectives }: FitnessRadarProps) {
  const primary = useCssVar("--color-primary");
  const gridColor = useCssVar("--color-on-surface", 0.08);
  const axisColor = useCssVar("--color-on-surface-dim");

  const data = Object.entries(objectives).map(([k, v]) => ({
    objective: k.replace(/_/g, " "),
    value: v,
  }));

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-xs text-on-surface-dim">
        No objective data yet.
      </div>
    );
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke={gridColor} />
          <PolarAngleAxis dataKey="objective" stroke={axisColor} fontSize={10} />
          <Radar dataKey="value" stroke={primary} fill={primary} fillOpacity={0.2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
