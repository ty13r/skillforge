import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

interface FitnessRadarProps {
  objectives: Record<string, number>;
}

export default function FitnessRadar({ objectives }: FitnessRadarProps) {
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
          <PolarGrid stroke="rgba(255,255,255,0.08)" />
          <PolarAngleAxis
            dataKey="objective"
            stroke="#9ba0b8"
            fontSize={10}
          />
          <Radar
            dataKey="value"
            stroke="#c0c1ff"
            fill="#c0c1ff"
            fillOpacity={0.2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
