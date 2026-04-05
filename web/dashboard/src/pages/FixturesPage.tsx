import { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { Calendar } from "lucide-react";
import { FdrDot } from "@/components/icons/FplIcons";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { FixtureTicker } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import { cn, fdrClass, CHART_COLORS, TOOLTIP_STYLE } from "@/lib/utils";

type SortMode = "alpha" | "difficulty";

export function FixturesPage() {
  const { data, loading, error } = useApi(() => api.fixtures(), [] as FixtureTicker[]);
  const [focusTeam, setFocusTeam] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("alpha");

  const { teams, gameweeks, grid, teamFdrSums } = useMemo(() => {
    const gws = [...new Set(data.map((f) => f.gameweek))].sort((a, b) => a - b);
    const teamSet = new Map<string, { name: string; id: number }>();
    data.forEach((f) => teamSet.set(f.team_short, { name: f.team_name, id: f.team_id }));

    const lookup = new Map<string, FixtureTicker>();
    data.forEach((f) => lookup.set(`${f.team_short}-${f.gameweek}`, f));

    const fdrSums = new Map<string, number>();
    teamSet.forEach((_, short) => {
      let sum = 0;
      gws.forEach((gw) => {
        const f = lookup.get(`${short}-${gw}`);
        sum += f?.fdr ?? 3;
      });
      fdrSums.set(short, sum);
    });

    const teamList = [...teamSet.entries()];
    if (sortMode === "alpha") {
      teamList.sort((a, b) => a[0].localeCompare(b[0]));
    } else {
      teamList.sort((a, b) => (fdrSums.get(a[0]) ?? 0) - (fdrSums.get(b[0]) ?? 0));
    }

    return { teams: teamList, gameweeks: gws, grid: lookup, teamFdrSums: fdrSums };
  }, [data, sortMode]);

  if (loading) return <TableSkeleton rows={20} />;
  if (error) return <ErrorCard message={error} />;

  const firstGw = gameweeks[0];

  return (
    <div className="space-y-4">
      <FixtureSwingChart gameweeks={gameweeks} teams={teams} grid={grid} />

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">Fixture Grid</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSortMode(sortMode === "alpha" ? "difficulty" : "alpha")}
            className="rounded-md px-3 py-1.5 text-xs font-medium bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--border)] transition-colors"
          >
            Sort: {sortMode === "alpha" ? "A-Z" : "Easiest first"}
          </button>
          <div className="flex gap-1.5 items-center text-xs text-[var(--muted-foreground)]" aria-label="FDR scale legend">
            <span>Easy</span>
            {([1, 2, 3, 4, 5] as const).map((fdr) => (
              <FdrDot key={fdr} level={fdr} size={18} />
            ))}
            <span>Hard</span>
          </div>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Fixture difficulty grid">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider sticky left-0 bg-[var(--card)] z-10 min-w-[100px]">
                    Team
                  </th>
                  {gameweeks.map((gw) => (
                    <th
                      key={gw}
                      className={cn(
                        "px-1 py-3 text-center text-xs font-medium uppercase tracking-wider min-w-[72px]",
                        gw === firstGw ? "text-[var(--accent)] font-bold" : "text-[var(--muted-foreground)]",
                      )}
                    >
                      GW{gw}
                      {gw === firstGw && <div className="h-0.5 bg-[var(--accent)] rounded mt-1 mx-2" />}
                    </th>
                  ))}
                  <th className="px-3 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider min-w-[50px]">
                    Sum
                  </th>
                </tr>
              </thead>
              <tbody>
                {teams.map(([short, info]) => {
                  const fdrSum = teamFdrSums.get(short) ?? 0;
                  const isFocused = focusTeam === short;
                  const isDimmed = focusTeam !== null && !isFocused;

                  return (
                    <tr
                      key={short}
                      className={cn(
                        "border-b border-[var(--border)] last:border-b-0 cursor-pointer transition-opacity",
                        isFocused && "bg-[var(--accent)]/5",
                        isDimmed && "opacity-40",
                      )}
                      onClick={() => setFocusTeam(focusTeam === short ? null : short)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setFocusTeam(focusTeam === short ? null : short);
                        }
                      }}
                    >
                      <td className="px-4 py-2 font-medium sticky left-0 bg-[var(--card)] z-10">
                        <div className="text-sm font-bold">{short}</div>
                        <div className="text-[10px] text-[var(--muted-foreground)]">{info.name}</div>
                      </td>
                      {gameweeks.map((gw) => {
                        const fixture = grid.get(`${short}-${gw}`);
                        if (!fixture) {
                          return (
                            <td key={gw} className="px-1 py-1 text-center text-xs text-[var(--muted-foreground)]">
                              -
                            </td>
                          );
                        }
                        return (
                          <td key={gw} className="px-1 py-1">
                            <div
                              className={cn(
                                "rounded-md px-2 py-2 text-center text-xs font-medium transition-all",
                                fdrClass(fixture.fdr),
                                gw === firstGw && "ring-2 ring-[var(--accent)] ring-offset-1",
                              )}
                            >
                              <div className="font-semibold">{fixture.opponent_short}</div>
                              <div className="text-[10px] opacity-80">
                                {fixture.is_home ? "H" : "A"} &middot; {fixture.fdr}
                              </div>
                            </div>
                          </td>
                        );
                      })}
                      <td className="px-3 py-2 text-center">
                        <span
                          className={cn(
                            "text-xs font-bold",
                            fdrSum / gameweeks.length <= 2.8
                              ? "text-green-600 dark:text-green-400"
                              : fdrSum / gameweeks.length >= 3.5
                                ? "text-red-500 dark:text-red-400"
                                : "text-[var(--muted-foreground)]",
                          )}
                        >
                          {fdrSum}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function FixtureSwingChart({
  gameweeks,
  teams,
  grid,
}: {
  gameweeks: number[];
  teams: [string, { name: string; id: number }][];
  grid: Map<string, FixtureTicker>;
}) {
  if (gameweeks.length < 3) return null;

  const teamAvgs = teams.map(([short]) => {
    const points = gameweeks.map((gw) => {
      const window = gameweeks.filter((g) => g >= gw && g < gw + 3);
      const fdrs = window.map((g) => grid.get(`${short}-${g}`)?.fdr ?? 3);
      return {
        gameweek: `GW${gw}`,
        fdr: fdrs.length > 0 ? fdrs.reduce((a, b) => a + b, 0) / fdrs.length : 3,
      };
    });
    const avgFdr = points.reduce((a, b) => a + b.fdr, 0) / points.length;
    return { short, points, avgFdr };
  });

  teamAvgs.sort((a, b) => a.avgFdr - b.avgFdr);
  const topTeams = teamAvgs.slice(0, 3);
  const bestTeam = topTeams[0];

  const chartData = gameweeks.map((gw) => {
    const point: Record<string, number | string> = { gameweek: `GW${gw}` };
    topTeams.forEach((t) => {
      const dp = t.points.find((p) => p.gameweek === `GW${gw}`);
      point[t.short] = dp?.fdr ?? 3;
    });
    return point;
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Fixture Difficulty</h1>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-l-4 border-l-green-500">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="h-4 w-4 text-green-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-green-600 dark:text-green-400">
                Best Upcoming Run
              </span>
            </div>
            <p className="text-xl font-bold">{bestTeam.short}</p>
            <p className="text-sm text-[var(--muted-foreground)]">
              Avg FDR {bestTeam.avgFdr.toFixed(1)} over next {gameweeks.length} GWs
            </p>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              Target their assets for easy points
            </p>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Rolling 3-GW FDR (Top 3 easiest)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
                <XAxis dataKey="gameweek" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
                <YAxis domain={[1, 5]} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} reversed />
                <ReferenceLine y={3} stroke="var(--border)" strokeDasharray="4 4" />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                {topTeams.map((t, i) => (
                  <Line
                    key={t.short}
                    type="monotone"
                    dataKey={t.short}
                    stroke={CHART_COLORS[i]}
                    strokeWidth={2.5}
                    dot={{ r: 3 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <div className="flex gap-4 justify-center mt-2 text-[10px] text-[var(--muted-foreground)]">
              {topTeams.map((t, i) => (
                <span key={t.short} className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: CHART_COLORS[i] }} />
                  {t.short}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
