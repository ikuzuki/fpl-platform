import { useEffect, useState } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  ReferenceLine,
  Label,
} from "recharts";
import { api } from "@/lib/api";
import type { TeamStrength } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { cn, scoreColor } from "@/lib/utils";

export function TeamsPage() {
  const [data, setData] = useState<TeamStrength[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.teams().then((d) => {
      setData(d.sort((a, b) => b.avg_fpl_score - a.avg_fpl_score));
      setLoading(false);
    });
  }, []);

  if (loading) return <TableSkeleton rows={10} />;

  // Compute medians for quadrant lines
  const scores = data.map((t) => t.avg_fpl_score);
  const fdrs = data
    .filter((t) => t.avg_fdr_remaining != null)
    .map((t) => t.avg_fdr_remaining!);
  const medianScore = scores.sort((a, b) => a - b)[Math.floor(scores.length / 2)] ?? 48;
  const medianFdr = fdrs.sort((a, b) => a - b)[Math.floor(fdrs.length / 2)] ?? 3.0;

  const scatterData = data
    .filter((t) => t.avg_fdr_remaining != null)
    .map((t) => ({
      ...t,
      x: t.avg_fdr_remaining!,
      y: t.avg_fpl_score,
    }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Team Analysis</h1>

      {/* Scatter plot: Score vs FDR */}
      <Card>
        <CardHeader>
          <CardTitle>Team Strength vs Fixture Difficulty</CardTitle>
          <p className="text-xs text-[var(--muted-foreground)]">
            Top-left quadrant = strong teams with easy fixtures (the sweet spot)
          </p>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={420}>
            <ScatterChart margin={{ top: 20, right: 30, bottom: 40, left: 20 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--border)"
                opacity={0.5}
              />
              <XAxis
                type="number"
                dataKey="x"
                name="FDR Remaining"
                domain={["auto", "auto"]}
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                reversed
              >
                <Label
                  value="Fixture Difficulty (lower = easier)"
                  position="bottom"
                  offset={20}
                  style={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                />
              </XAxis>
              <YAxis
                type="number"
                dataKey="y"
                name="Avg FPL Score"
                domain={["auto", "auto"]}
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              >
                <Label
                  value="Avg FPL Score"
                  angle={-90}
                  position="insideLeft"
                  offset={-5}
                  style={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                />
              </YAxis>
              <ReferenceLine
                y={medianScore}
                stroke="var(--border)"
                strokeDasharray="4 4"
              />
              <ReferenceLine
                x={medianFdr}
                stroke="var(--border)"
                strokeDasharray="4 4"
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.[0]) return null;
                  const team = payload[0].payload as TeamStrength & {
                    x: number;
                    y: number;
                  };
                  return (
                    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 shadow-lg text-sm">
                      <p className="font-bold">{team.team_name}</p>
                      <p className="text-[var(--muted-foreground)]">
                        Avg Score: {team.avg_fpl_score} &middot; FDR:{" "}
                        {team.avg_fdr_remaining?.toFixed(1)}
                      </p>
                      <p className="text-[var(--muted-foreground)]">
                        Form: {team.avg_form} &middot; Value: &pound;
                        {team.squad_value.toFixed(1)}m
                      </p>
                      <p className="text-[var(--muted-foreground)]">
                        Top: {team.top_scorer_name} ({team.top_scorer_points}{" "}
                        pts)
                      </p>
                    </div>
                  );
                }}
              />
              <Scatter data={scatterData} fill="var(--accent)">
                {scatterData.map((entry) => (
                  <Cell
                    key={entry.team_id}
                    fill={
                      entry.avg_fpl_score >= medianScore &&
                      entry.avg_fdr_remaining! <= medianFdr
                        ? "oklch(0.6 0.18 145)"
                        : entry.avg_fpl_score < medianScore &&
                            entry.avg_fdr_remaining! > medianFdr
                          ? "oklch(0.6 0.18 25)"
                          : "var(--accent)"
                    }
                    r={8}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          {/* Team labels overlay */}
          <div className="flex flex-wrap gap-2 mt-2 justify-center">
            {scatterData.map((t) => (
              <span
                key={t.team_id}
                className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--muted)] text-[var(--muted-foreground)]"
              >
                {t.team_short}: {t.avg_fpl_score} / {t.avg_fdr_remaining?.toFixed(1)}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Team Table */}
      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  Team
                </th>
                <th className="px-3 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  Score
                </th>
                <th className="px-3 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  Points
                </th>
                <th className="px-3 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  Form
                </th>
                <th className="px-3 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  Value
                </th>
                <th className="px-3 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  FDR
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  Top Scorer
                </th>
                <th className="px-3 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase">
                  Players
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((team) => (
                <tr
                  key={team.team_id}
                  className="border-b border-[var(--border)] hover:bg-[var(--muted)]/50 transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="font-bold">{team.team_short}</div>
                    <div className="text-[10px] text-[var(--muted-foreground)]">
                      {team.team_name}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span
                      className={cn(
                        "font-bold text-lg",
                        scoreColor(team.avg_fpl_score),
                      )}
                    >
                      {team.avg_fpl_score}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center font-medium">
                    {team.total_points}
                  </td>
                  <td className="px-3 py-3 text-center">{team.avg_form}</td>
                  <td className="px-3 py-3 text-center">
                    &pound;{team.squad_value.toFixed(1)}m
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span
                      className={cn(
                        "font-medium",
                        team.avg_fdr_remaining != null &&
                          team.avg_fdr_remaining <= 2.8
                          ? "text-green-600 dark:text-green-400"
                          : team.avg_fdr_remaining != null &&
                              team.avg_fdr_remaining >= 3.5
                            ? "text-red-500 dark:text-red-400"
                            : "",
                      )}
                    >
                      {team.avg_fdr_remaining?.toFixed(1) ?? "-"}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    {team.top_scorer_name}{" "}
                    <span className="text-[var(--muted-foreground)]">
                      ({team.top_scorer_points})
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center text-[var(--muted-foreground)]">
                    {team.enriched_player_count}/{team.player_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
