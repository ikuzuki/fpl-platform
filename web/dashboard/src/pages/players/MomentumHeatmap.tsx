import { useMemo, useState } from "react";
import type { PlayerHistory } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, positionColor } from "@/lib/utils";
import { MetricIcons } from "@/components/icons/FplIcons";

function scoreToColor(score: number): string {
  if (score >= 70) return "bg-[var(--accent)] text-white";
  if (score >= 60) return "bg-[var(--accent)]/70 text-white";
  if (score >= 50) return "bg-[var(--accent)]/40 text-[var(--foreground)]";
  if (score >= 40) return "bg-[var(--accent)]/20 text-[var(--foreground)]";
  if (score >= 30) return "bg-[var(--muted)] text-[var(--muted-foreground)]";
  return "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300";
}

export function MomentumHeatmap({ history }: { history: PlayerHistory[] }) {
  const [hoveredPlayer, setHoveredPlayer] = useState<number | null>(null);

  const gameweeks = useMemo(
    () => [...new Set(history.map((r) => r.gameweek))].sort((a, b) => a - b),
    [history],
  );

  const latestGw = gameweeks[gameweeks.length - 1];

  const players = useMemo(() => {
    const latest = history
      .filter((r) => r.gameweek === latestGw)
      .sort((a, b) => a.fpl_score_rank - b.fpl_score_rank)
      .slice(0, 50);
    return latest;
  }, [history, latestGw]);

  const lookup = useMemo(() => {
    const map = new Map<string, PlayerHistory>();
    history.forEach((r) => map.set(`${r.player_id}-${r.gameweek}`, r));
    return map;
  }, [history]);

  if (gameweeks.length < 2 || players.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-1.5">
          <MetricIcons.Momentum size={16} />
          Gameweek Momentum
        </CardTitle>
        <p className="text-xs text-[var(--muted-foreground)]">
          FPL Score by player per gameweek. Darker = stronger. Hover to highlight a player.
        </p>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="text-[10px]" aria-label="Player momentum heatmap">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)] uppercase sticky left-0 bg-[var(--card)] z-10 min-w-[120px]">
                  Player
                </th>
                {gameweeks.map((gw) => (
                  <th key={gw} className="px-0.5 py-2 text-center font-medium text-[var(--muted-foreground)] min-w-[32px]">
                    {gw}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {players.map((p) => {
                const isDimmed = hoveredPlayer !== null && hoveredPlayer !== p.player_id;
                return (
                  <tr
                    key={p.player_id}
                    className={cn("transition-opacity", isDimmed && "opacity-30")}
                    onMouseEnter={() => setHoveredPlayer(p.player_id)}
                    onMouseLeave={() => setHoveredPlayer(null)}
                  >
                    <td className="px-3 py-0.5 sticky left-0 bg-[var(--card)] z-10">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium truncate max-w-[70px]">{p.web_name}</span>
                        <Badge className={cn(positionColor(p.position), "text-[8px] px-1 py-0")}>{p.position}</Badge>
                      </div>
                    </td>
                    {gameweeks.map((gw) => {
                      const row = lookup.get(`${p.player_id}-${gw}`);
                      const score = row?.fpl_score;
                      return (
                        <td key={gw} className="px-0.5 py-0.5">
                          {score != null ? (
                            <div
                              className={cn(
                                "w-7 h-5 rounded-sm flex items-center justify-center font-medium",
                                scoreToColor(score),
                              )}
                              title={`${p.web_name} GW${gw}: ${score.toFixed(1)}`}
                            >
                              {Math.round(score)}
                            </div>
                          ) : (
                            <div className="w-7 h-5 rounded-sm bg-[var(--muted)]/30" />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-2 px-6 py-3 text-[10px] text-[var(--muted-foreground)] border-t border-[var(--border)]">
          <span>Score:</span>
          {[
            { label: "70+", cls: "bg-[var(--accent)] text-white" },
            { label: "60", cls: "bg-[var(--accent)]/70 text-white" },
            { label: "50", cls: "bg-[var(--accent)]/40" },
            { label: "40", cls: "bg-[var(--accent)]/20" },
            { label: "30", cls: "bg-[var(--muted)]" },
            { label: "<30", cls: "bg-red-100 dark:bg-red-900/30" },
          ].map((tier) => (
            <div key={tier.label} className="flex items-center gap-1">
              <div className={cn("w-4 h-3 rounded-sm", tier.cls)} />
              <span>{tier.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
