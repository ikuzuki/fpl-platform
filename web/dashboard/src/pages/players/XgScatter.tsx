import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  CartesianGrid,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  Cell,
  ReferenceLine,
  Label,
  LabelList,
} from "recharts";
import type { PlayerDashboard } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { POS_CHART_COLORS, TOOLTIP_STYLE } from "@/lib/utils";
import { MetricIcons } from "@/components/icons/FplIcons";

export function XgScatter({ players }: { players: PlayerDashboard[] }) {
  const withXg = players.filter((p) => p.xg != null);
  if (withXg.length < 5) return null;

  const scatterData = withXg.map((p) => ({
    x: p.xg!,
    y: p.goals_scored,
    name: p.web_name,
    position: p.position,
    minutes: p.minutes,
    delta: Math.abs(p.goals_scored - p.xg!),
  }));

  const maxVal = Math.max(...scatterData.map((d) => Math.max(d.x, d.y)), 1);

  // Label top 5 outliers by distance from the reference line
  const outlierNames = new Set(
    [...scatterData]
      .sort((a, b) => b.delta - a.delta)
      .slice(0, 5)
      .map((d) => d.name),
  );

  const labelledData = scatterData.map((d) => ({
    ...d,
    label: outlierNames.has(d.name) ? d.name : "",
  }));

  return (
    <Card>
      <CardContent className="pt-4">
        <h3 className="font-semibold mb-1 flex items-center gap-1.5">
          <MetricIcons.ExpectedGoals size={16} />
          xG Efficiency
        </h3>
        <p className="text-xs text-[var(--muted-foreground)] mb-3">
          Above the line = clinical. Below = wasteful. Size = minutes played.
        </p>
        <ResponsiveContainer width="100%" height={350}>
          <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
            <XAxis type="number" dataKey="x" name="xG" domain={[0, maxVal]} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}>
              <Label value="Expected Goals (xG)" position="bottom" offset={15} style={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            </XAxis>
            <YAxis type="number" dataKey="y" name="Goals" domain={[0, maxVal]} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}>
              <Label value="Actual Goals" angle={-90} position="insideLeft" offset={-5} style={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            </YAxis>
            <ZAxis type="number" dataKey="minutes" range={[30, 200]} name="Minutes" />
            <ReferenceLine
              segment={[{ x: 0, y: 0 }, { x: maxVal, y: maxVal }]}
              stroke="var(--muted-foreground)"
              strokeDasharray="4 4"
              opacity={0.5}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const d = payload[0].payload;
                return (
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 shadow-lg text-xs" style={TOOLTIP_STYLE}>
                    <p className="font-semibold">{d.name} ({d.position})</p>
                    <p className="text-[var(--muted-foreground)]">Goals: {d.y} | xG: {d.x.toFixed(1)} | Mins: {d.minutes}</p>
                  </div>
                );
              }}
            />
            <Scatter data={labelledData}>
              {labelledData.map((d, i) => (
                <Cell key={i} fill={POS_CHART_COLORS[d.position] ?? "var(--accent)"} opacity={0.7} />
              ))}
              <LabelList dataKey="label" position="top" offset={8} style={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
        <div className="flex items-center gap-4 mt-2 text-[10px] text-[var(--muted-foreground)] justify-center">
          {Object.entries(POS_CHART_COLORS).map(([pos, color]) => (
            <span key={pos} className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: color }} />
              {pos}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
