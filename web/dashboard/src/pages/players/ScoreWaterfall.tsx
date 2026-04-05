import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";
import type { PlayerDashboard } from "@/lib/types";
import { SCORE_COMPONENTS, TOOLTIP_STYLE } from "@/lib/utils";

export function ScoreWaterfall({ player }: { player: PlayerDashboard }) {
  const components = SCORE_COMPONENTS.map((c) => ({
    name: c.label,
    value: (player[c.key as keyof PlayerDashboard] as number | null) ?? 0,
    color: c.color,
  })).filter((c) => c.value > 0);

  if (components.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={components.length * 28 + 20}>
      <BarChart data={components} layout="vertical" margin={{ left: 60, right: 30 }}>
        <XAxis type="number" domain={[0, "auto"]} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
        <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value) => Number(value).toFixed(1)}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {components.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
