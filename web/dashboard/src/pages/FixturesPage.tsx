import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { FixtureTicker } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { cn, fdrClass } from "@/lib/utils";

export function FixturesPage() {
  const [data, setData] = useState<FixtureTicker[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fixtures().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  const { teams, gameweeks, grid } = useMemo(() => {
    const gws = [...new Set(data.map((f) => f.gameweek))].sort((a, b) => a - b);
    const teamSet = new Map<string, { name: string; id: number }>();
    data.forEach((f) => teamSet.set(f.team_short, { name: f.team_name, id: f.team_id }));
    const teamList = [...teamSet.entries()].sort((a, b) => a[0].localeCompare(b[0]));

    const lookup = new Map<string, FixtureTicker>();
    data.forEach((f) => lookup.set(`${f.team_short}-${f.gameweek}`, f));

    return { teams: teamList, gameweeks: gws, grid: lookup };
  }, [data]);

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--muted-foreground)]">Loading fixtures...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Fixture Difficulty</h1>
        <div className="flex gap-2 items-center text-xs text-[var(--muted-foreground)]">
          <span>Easy</span>
          {[1, 2, 3, 4, 5].map((fdr) => (
            <div key={fdr} className={cn("w-6 h-4 rounded text-[10px] flex items-center justify-center", fdrClass(fdr))}>
              {fdr}
            </div>
          ))}
          <span>Hard</span>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider sticky left-0 bg-[var(--card)] z-10">
                    Team
                  </th>
                  {gameweeks.map((gw) => (
                    <th
                      key={gw}
                      className="px-2 py-3 text-center text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider min-w-[64px]"
                    >
                      GW{gw}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {teams.map(([short, info]) => (
                  <tr key={short} className="border-b border-[var(--border)] last:border-b-0">
                    <td className="px-4 py-2 font-medium sticky left-0 bg-[var(--card)] z-10">
                      <div className="text-sm">{short}</div>
                      <div className="text-[10px] text-[var(--muted-foreground)]">{info.name}</div>
                    </td>
                    {gameweeks.map((gw) => {
                      const fixture = grid.get(`${short}-${gw}`);
                      if (!fixture) {
                        return <td key={gw} className="px-2 py-2 text-center text-xs text-[var(--muted-foreground)]">-</td>;
                      }
                      return (
                        <td key={gw} className="px-1 py-1">
                          <div
                            className={cn(
                              "rounded-md px-2 py-1.5 text-center text-xs font-medium",
                              fdrClass(fixture.fdr),
                            )}
                          >
                            <div>{fixture.opponent_short}</div>
                            <div className="text-[10px] opacity-80">
                              {fixture.is_home ? "H" : "A"}
                            </div>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
