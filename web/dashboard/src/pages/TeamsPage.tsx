import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { api } from "@/lib/api";
import type { TeamStrength } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--muted-foreground)]">Loading teams...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Team Strength</h1>

      <Card>
        <CardHeader>
          <CardTitle>Average FPL Score by Team</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={data} layout="vertical" margin={{ left: 40, right: 20 }}>
              <XAxis type="number" domain={[0, 80]} tick={{ fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="team_short"
                width={40}
                tick={{ fontSize: 12 }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.[0]) return null;
                  const team = payload[0].payload as TeamStrength;
                  return (
                    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 shadow-lg text-sm">
                      <p className="font-semibold">{team.team_name}</p>
                      <p className="text-[var(--muted-foreground)]">
                        Avg Score: {team.avg_fpl_score} &middot; Form: {team.avg_form}
                      </p>
                      <p className="text-[var(--muted-foreground)]">
                        Top: {team.top_scorer_name} ({team.top_scorer_points} pts)
                      </p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="avg_fpl_score" radius={[0, 4, 4, 0]}>
                {data.map((entry) => (
                  <Cell
                    key={entry.team_id}
                    fill={
                      entry.avg_fpl_score >= 52
                        ? "oklch(0.65 0.18 145)"
                        : entry.avg_fpl_score >= 44
                          ? "oklch(0.55 0.15 265)"
                          : "oklch(0.65 0.15 25)"
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {data.map((team) => (
          <Card key={team.team_id} className="hover:shadow-md transition-shadow">
            <CardContent className="pt-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="font-bold text-lg">{team.team_short}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">{team.team_name}</p>
                </div>
                <div className={cn("text-2xl font-bold", scoreColor(team.avg_fpl_score))}>
                  {team.avg_fpl_score}
                </div>
              </div>
              <dl className="space-y-1.5 text-xs text-[var(--muted-foreground)]">
                <div className="flex justify-between">
                  <dt>Total Points</dt>
                  <dd className="font-medium text-[var(--foreground)]">{team.total_points}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Avg Form</dt>
                  <dd className="font-medium text-[var(--foreground)]">{team.avg_form}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Squad Value</dt>
                  <dd className="font-medium text-[var(--foreground)]">
                    &pound;{team.squad_value.toFixed(1)}m
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt>FDR Remaining</dt>
                  <dd className="font-medium text-[var(--foreground)]">
                    {team.avg_fdr_remaining?.toFixed(1) ?? "-"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt>Top Scorer</dt>
                  <dd className="font-medium text-[var(--foreground)]">
                    {team.top_scorer_name} ({team.top_scorer_points})
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
