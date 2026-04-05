import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import { Sparkles } from "lucide-react";
import type { PlayerDashboard } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { formatNumber, fdrClass, cn } from "@/lib/utils";
import { ScoreWaterfall } from "./ScoreWaterfall";

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between">
      <dt>{label}</dt>
      <dd className="font-medium text-[var(--foreground)]">{value}</dd>
    </div>
  );
}

export function PlayerDetail({ player }: { player: PlayerDashboard }) {
  const radarData = [
    { stat: "Goals", value: player.goals_scored, max: Math.max(player.goals_scored, 20) },
    { stat: "Assists", value: player.assists, max: Math.max(player.assists, 15) },
    { stat: "xG", value: player.xg ?? player.goals_scored * 0.8, max: 20 },
    { stat: "Creativity", value: player.creativity / 10, max: 100 },
    { stat: "Threat", value: player.threat / 10, max: 100 },
    { stat: "ICT", value: player.ict_index / 3, max: 100 },
  ].map((d) => ({
    ...d,
    normalized: Math.min((d.value / d.max) * 100, 100),
  }));

  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
      {/* AI Summary Card */}
      <div className="md:col-span-4">
        <div className="rounded-lg border border-[var(--ai-border)] bg-[var(--ai-bg)] p-4">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="h-4 w-4 text-[var(--accent)]" />
            <h4 className="font-semibold text-sm">AI Analysis</h4>
          </div>
          <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
            {player.llm_summary ?? "No AI summary available for this player."}
          </p>
          {player.key_themes && player.key_themes.length > 0 && (
            <div className="flex gap-1.5 mt-3 flex-wrap">
              {player.key_themes.map((t) => (
                <Badge key={t} className="bg-[var(--muted)] text-[var(--muted-foreground)]">
                  {t}
                </Badge>
              ))}
            </div>
          )}
          {player.injury_reasoning && (
            <div className="mt-3 pt-3 border-t border-[var(--ai-border)]">
              <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">
                Injury Assessment
              </p>
              <p className="text-sm text-[var(--muted-foreground)]">
                {player.injury_reasoning}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Score Breakdown + Radar */}
      <div className="md:col-span-4">
        <h4 className="font-semibold text-sm mb-2">Score Breakdown</h4>
        <ScoreWaterfall player={player} />
        <h4 className="font-semibold text-sm mb-2 mt-4">Player Profile</h4>
        <ResponsiveContainer width="100%" height={220}>
          <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
            <PolarGrid stroke="var(--border)" />
            <PolarAngleAxis
              dataKey="stat"
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            />
            <Radar
              dataKey="normalized"
              stroke="var(--accent)"
              fill="var(--accent)"
              fillOpacity={0.2}
              strokeWidth={2}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Stats + Fixture Strip */}
      <div className="md:col-span-4">
        <h4 className="font-semibold text-sm mb-2">Key Stats</h4>
        <dl className="space-y-1.5 text-sm text-[var(--muted-foreground)]">
          <StatRow label="Goals" value={player.goals_scored} />
          <StatRow label="Assists" value={player.assists} />
          <StatRow label="Clean sheets" value={player.clean_sheets} />
          <StatRow label="xG" value={player.xg?.toFixed(1) ?? "n/a"} />
          <StatRow label="xA" value={player.xa?.toFixed(1) ?? "n/a"} />
          <StatRow
            label="xG delta"
            value={
              player.xg_delta != null
                ? `${player.xg_delta > 0 ? "+" : ""}${player.xg_delta.toFixed(1)}`
                : "n/a"
            }
          />
          <StatRow label="Net transfers" value={formatNumber(player.net_transfers)} />
        </dl>

        {player.fixture_recommendation && (
          <div className="mt-4">
            <h4 className="font-semibold text-sm mb-2">Fixture Outlook</h4>
            <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
              {player.fixture_recommendation}
            </p>
            {player.best_gameweeks && player.best_gameweeks.length > 0 && (
              <div className="flex gap-1.5 mt-2">
                {player.best_gameweeks.map((gw) => (
                  <span
                    key={gw}
                    className={cn("rounded px-2 py-0.5 text-xs font-medium", fdrClass(2))}
                  >
                    GW{gw}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
