import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { FixtureTicker } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { cn, fdrClass } from "@/lib/utils";

type SortMode = "alpha" | "difficulty";

export function FixturesPage() {
  const [data, setData] = useState<FixtureTicker[]>([]);
  const [loading, setLoading] = useState(true);
  const [focusTeam, setFocusTeam] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("alpha");

  useEffect(() => {
    api.fixtures().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  const { teams, gameweeks, grid, teamFdrSums } = useMemo(() => {
    const gws = [...new Set(data.map((f) => f.gameweek))].sort(
      (a, b) => a - b,
    );
    const teamSet = new Map<string, { name: string; id: number }>();
    data.forEach((f) =>
      teamSet.set(f.team_short, { name: f.team_name, id: f.team_id }),
    );

    const lookup = new Map<string, FixtureTicker>();
    data.forEach((f) => lookup.set(`${f.team_short}-${f.gameweek}`, f));

    // Compute total FDR per team
    const fdrSums = new Map<string, number>();
    teamSet.forEach((_, short) => {
      let sum = 0;
      gws.forEach((gw) => {
        const f = lookup.get(`${short}-${gw}`);
        sum += f?.fdr ?? 3;
      });
      fdrSums.set(short, sum);
    });

    let teamList = [...teamSet.entries()];
    if (sortMode === "alpha") {
      teamList.sort((a, b) => a[0].localeCompare(b[0]));
    } else {
      teamList.sort(
        (a, b) => (fdrSums.get(a[0]) ?? 0) - (fdrSums.get(b[0]) ?? 0),
      );
    }

    return {
      teams: teamList,
      gameweeks: gws,
      grid: lookup,
      teamFdrSums: fdrSums,
    };
  }, [data, sortMode]);

  if (loading) return <TableSkeleton rows={20} />;

  const firstGw = gameweeks[0];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">Fixture Difficulty</h1>
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <button
              onClick={() =>
                setSortMode(sortMode === "alpha" ? "difficulty" : "alpha")
              }
              className="rounded-md px-3 py-1.5 text-xs font-medium bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--border)] transition-colors"
            >
              Sort: {sortMode === "alpha" ? "A-Z" : "Easiest first"}
            </button>
          </div>
          <div className="flex gap-1.5 items-center text-xs text-[var(--muted-foreground)]">
            <span>Easy</span>
            {[1, 2, 3, 4, 5].map((fdr) => (
              <div
                key={fdr}
                className={cn(
                  "w-6 h-5 rounded text-[10px] flex items-center justify-center font-medium",
                  fdrClass(fdr),
                )}
              >
                {fdr}
              </div>
            ))}
            <span>Hard</span>
          </div>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
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
                        gw === firstGw
                          ? "text-[var(--accent)] font-bold"
                          : "text-[var(--muted-foreground)]",
                      )}
                    >
                      GW{gw}
                      {gw === firstGw && (
                        <div className="h-0.5 bg-[var(--accent)] rounded mt-1 mx-2" />
                      )}
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
                      onClick={() =>
                        setFocusTeam(focusTeam === short ? null : short)
                      }
                    >
                      <td className="px-4 py-2 font-medium sticky left-0 bg-[var(--card)] z-10">
                        <div className="text-sm font-bold">{short}</div>
                        <div className="text-[10px] text-[var(--muted-foreground)]">
                          {info.name}
                        </div>
                      </td>
                      {gameweeks.map((gw) => {
                        const fixture = grid.get(`${short}-${gw}`);
                        if (!fixture) {
                          return (
                            <td
                              key={gw}
                              className="px-1 py-1 text-center text-xs text-[var(--muted-foreground)]"
                            >
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
                              <div className="font-semibold">
                                {fixture.opponent_short}
                              </div>
                              <div className="text-[10px] opacity-80">
                                {fixture.is_home ? "H" : "A"}
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
