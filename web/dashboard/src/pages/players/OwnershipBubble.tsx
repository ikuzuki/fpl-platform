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

export function OwnershipBubble({ players }: { players: PlayerDashboard[] }) {
  const scatterData = players.map((p) => ({
    x: p.ownership_pct,
    y: p.points_per_million,
    z: p.total_points,
    name: p.web_name,
    position: p.position,
  }));

  const medianOwn = [...scatterData].sort((a, b) => a.x - b.x)[Math.floor(scatterData.length / 2)]?.x ?? 10;
  const medianPpm = [...scatterData].sort((a, b) => a.y - b.y)[Math.floor(scatterData.length / 2)]?.y ?? 15;

  // Label outliers: top 3 differentials (low ownership, high value) and top 2 traps (high ownership, low value)
  const differentials = [...scatterData]
    .filter((d) => d.x < medianOwn && d.y > medianPpm)
    .sort((a, b) => b.y - a.y)
    .slice(0, 3)
    .map((d) => d.name);
  const traps = [...scatterData]
    .filter((d) => d.x > medianOwn && d.y < medianPpm)
    .sort((a, b) => a.y - b.y)
    .slice(0, 2)
    .map((d) => d.name);
  const outlierNames = new Set([...differentials, ...traps]);

  const labelledData = scatterData.map((d) => ({
    ...d,
    label: outlierNames.has(d.name) ? d.name : "",
  }));

  return (
    <Card>
      <CardContent className="pt-4">
        <h3 className="font-semibold mb-1 flex items-center gap-1.5">
          <MetricIcons.Ownership size={16} />
          Ownership vs Value
        </h3>
        <p className="text-xs text-[var(--muted-foreground)] mb-3">
          Top-left = differentials (high value, low ownership). Bottom-right = traps. Size = total points.
        </p>
        <ResponsiveContainer width="100%" height={350}>
          <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
            <XAxis type="number" dataKey="x" name="Ownership" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}>
              <Label value="Ownership %" position="bottom" offset={15} style={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            </XAxis>
            <YAxis type="number" dataKey="y" name="Pts/M" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}>
              <Label value="Points per Million" angle={-90} position="insideLeft" offset={-5} style={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            </YAxis>
            <ZAxis type="number" dataKey="z" range={[20, 150]} name="Total Points" />
            <ReferenceLine x={medianOwn} stroke="var(--border)" strokeDasharray="4 4" />
            <ReferenceLine y={medianPpm} stroke="var(--border)" strokeDasharray="4 4" />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const d = payload[0].payload;
                return (
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 shadow-lg text-xs" style={TOOLTIP_STYLE}>
                    <p className="font-semibold">{d.name} ({d.position})</p>
                    <p className="text-[var(--muted-foreground)]">Own: {d.x.toFixed(1)}% | Pts/M: {d.y.toFixed(1)} | Pts: {d.z}</p>
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
