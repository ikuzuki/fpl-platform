import { useMemo } from "react";
import { Crown, TrendingUp, Target, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { PlayerDashboard } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import {
  cn,
  formatPrice,
  positionColor,
  scoreColor,
  scoreBarColor,
  heatmapBg,
  fdrClass,
} from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Captain score types & computation                                  */
/* ------------------------------------------------------------------ */

interface CaptainCandidate {
  player: PlayerDashboard;
  captainScore: number;
  formNorm: number;
  xgPerNinetyNorm: number;
  fixtureNorm: number;
  pointsNorm: number;
  ownershipNorm: number;
}

const WEIGHTS = {
  form: 0.3,
  xg: 0.2,
  fixture: 0.2,
  points: 0.15,
  ownership: 0.15,
} as const;

const FACTOR_COLORS = [
  { key: "formNorm", label: "Form", color: "var(--chart-1)" },
  { key: "xgPerNinetyNorm", label: "xG/90", color: "var(--chart-2)" },
  { key: "fixtureNorm", label: "Fixtures", color: "var(--chart-3)" },
  { key: "pointsNorm", label: "Points", color: "var(--chart-4)" },
  { key: "ownershipNorm", label: "Own%", color: "var(--chart-5)" },
] as const;

function minMaxNorm(value: number, min: number, max: number): number {
  if (max === min) return 50;
  return ((value - min) / (max - min)) * 100;
}

function computeCandidates(players: PlayerDashboard[]): CaptainCandidate[] {
  // Only consider players with meaningful minutes (>= 270 = ~3 full games)
  const eligible = players.filter(
    (p) => p.minutes >= 270 && (p.position === "MID" || p.position === "FWD" || p.position === "DEF"),
  );

  if (eligible.length === 0) return [];

  // Derive raw values
  const ppgValues = eligible.map((p) => p.points_per_game);
  const xgPer90Values = eligible.map((p) =>
    p.xg != null && p.minutes > 0 ? (p.xg / p.minutes) * 90 : 0,
  );
  const totalPtsValues = eligible.map((p) => p.total_points);

  const ppgMin = Math.min(...ppgValues);
  const ppgMax = Math.max(...ppgValues);
  const xgMin = Math.min(...xgPer90Values);
  const xgMax = Math.max(...xgPer90Values);
  const ptsMin = Math.min(...totalPtsValues);
  const ptsMax = Math.max(...totalPtsValues);

  return eligible.map((p, idx) => {
    const formNorm = minMaxNorm(p.points_per_game, ppgMin, ppgMax);
    const xgPerNinetyNorm = minMaxNorm(xgPer90Values[idx], xgMin, xgMax);
    const fixtureNorm =
      p.fdr_next_3 != null ? ((5 - p.fdr_next_3) / 4) * 100 : 50;
    const pointsNorm = minMaxNorm(p.total_points, ptsMin, ptsMax);
    const ownershipNorm = Math.min(p.ownership_pct, 100);

    const captainScore =
      formNorm * WEIGHTS.form +
      xgPerNinetyNorm * WEIGHTS.xg +
      fixtureNorm * WEIGHTS.fixture +
      pointsNorm * WEIGHTS.points +
      ownershipNorm * WEIGHTS.ownership;

    return {
      player: p,
      captainScore,
      formNorm,
      xgPerNinetyNorm,
      fixtureNorm,
      pointsNorm,
      ownershipNorm,
    };
  });
}

/* ------------------------------------------------------------------ */
/*  Page component                                                     */
/* ------------------------------------------------------------------ */

export function CaptainPage() {
  const {
    data: players,
    loading,
    error,
  } = useApi(api.players, [] as PlayerDashboard[]);

  const candidates = useMemo(() => {
    if (players.length === 0) return [];
    return computeCandidates(players).sort(
      (a, b) => b.captainScore - a.captainScore,
    );
  }, [players]);

  const top15 = candidates.slice(0, 15);
  const topPick = top15[0] ?? null;

  // Differential picks: <10% ownership but in top 25 by captain score
  const differentials = useMemo(
    () =>
      candidates
        .slice(0, 25)
        .filter((c) => c.player.ownership_pct < 10),
    [candidates],
  );

  // Ranges for heatmap colouring within the top 15
  const ranges = useMemo(() => {
    if (top15.length === 0) return null;
    const vals = (fn: (c: CaptainCandidate) => number) => {
      const v = top15.map(fn);
      return { min: Math.min(...v), max: Math.max(...v) };
    };
    return {
      score: vals((c) => c.captainScore),
      form: vals((c) => c.player.points_per_game),
      xg: vals((c) => c.xgPerNinetyNorm),
      fixture: vals((c) => c.fixtureNorm),
      points: vals((c) => c.player.total_points),
      ownership: vals((c) => c.player.ownership_pct),
    };
  }, [top15]);

  const gameweek = players[0]?.gameweek ?? "?";

  if (loading) return <TableSkeleton rows={12} />;
  if (error) return <ErrorCard message={error} />;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Crown className="h-6 w-6 text-amber-500" />
          Captain Picker
        </h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          GW{gameweek} &mdash; Who to captain this week
        </p>
      </div>

      {/* Hero — Top Pick */}
      {topPick && <TopPickHero candidate={topPick} />}

      {/* Decision Matrix Table */}
      {ranges && (
        <Card>
          <div className="overflow-x-auto">
            <table
              className="w-full text-sm"
              aria-label="Captain candidates decision matrix"
            >
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {[
                    { label: "#", width: 40 },
                    { label: "Player", width: 160 },
                    { label: "Captain Score", width: 130, sort: true },
                    { label: "Form", width: 65, sort: true },
                    { label: "xG/90", width: 70, sort: true },
                    { label: "Fixtures", width: 75, sort: true },
                    { label: "Points", width: 65, sort: true },
                    { label: "Own%", width: 65, sort: true },
                    { label: "Factors", width: 140 },
                  ].map((col) => (
                    <th
                      key={col.label}
                      className="px-3 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider select-none"
                      style={{ width: col.width }}
                      tabIndex={col.sort ? 0 : undefined}
                      aria-sort={col.sort ? "none" : undefined}
                    >
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {top15.map((c, idx) => (
                  <tr
                    key={c.player.player_id}
                    className="border-b border-[var(--border)] hover:bg-[var(--muted)]/50 transition-colors"
                    tabIndex={0}
                  >
                    {/* Rank */}
                    <td className="px-3 py-2.5 text-xs font-mono text-[var(--muted-foreground)]">
                      {idx + 1}
                    </td>

                    {/* Player */}
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div>
                          <span className="font-medium">
                            {c.player.web_name}
                          </span>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="text-xs text-[var(--muted-foreground)]">
                              {c.player.team_short}
                            </span>
                            <Badge
                              className={cn(
                                "text-[10px] px-1.5 py-0",
                                positionColor(c.player.position),
                              )}
                            >
                              {c.player.position}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Captain Score */}
                    <td
                      className={cn(
                        "px-3 py-2.5",
                        heatmapBg(
                          c.captainScore,
                          ranges.score.min,
                          ranges.score.max,
                        ),
                      )}
                    >
                      <div>
                        <span
                          className={cn(
                            "font-bold text-sm",
                            scoreColor(c.captainScore),
                          )}
                        >
                          {c.captainScore.toFixed(1)}
                        </span>
                        <div
                          className={cn("score-bar", scoreBarColor(c.captainScore))}
                          style={{ width: `${Math.min(c.captainScore, 100)}%` }}
                        />
                      </div>
                    </td>

                    {/* Form (ppg) */}
                    <td
                      className={cn(
                        "px-3 py-2.5",
                        heatmapBg(
                          c.player.points_per_game,
                          ranges.form.min,
                          ranges.form.max,
                        ),
                      )}
                    >
                      {c.player.points_per_game.toFixed(1)}
                    </td>

                    {/* xG/90 */}
                    <td
                      className={cn(
                        "px-3 py-2.5",
                        heatmapBg(
                          c.xgPerNinetyNorm,
                          ranges.xg.min,
                          ranges.xg.max,
                        ),
                      )}
                    >
                      {c.player.xg != null && c.player.minutes > 0
                        ? ((c.player.xg / c.player.minutes) * 90).toFixed(2)
                        : "-"}
                    </td>

                    {/* Fixtures (FDR badge) */}
                    <td
                      className={cn(
                        "px-3 py-2.5",
                        heatmapBg(
                          c.fixtureNorm,
                          ranges.fixture.min,
                          ranges.fixture.max,
                        ),
                      )}
                    >
                      {c.player.fdr_next_3 != null ? (
                        <span
                          className={cn(
                            "rounded px-2 py-0.5 text-xs font-medium",
                            fdrClass(c.player.fdr_next_3),
                          )}
                        >
                          {c.player.fdr_next_3.toFixed(1)}
                        </span>
                      ) : (
                        "-"
                      )}
                    </td>

                    {/* Points */}
                    <td
                      className={cn(
                        "px-3 py-2.5",
                        heatmapBg(
                          c.player.total_points,
                          ranges.points.min,
                          ranges.points.max,
                        ),
                      )}
                    >
                      {c.player.total_points}
                    </td>

                    {/* Ownership */}
                    <td
                      className={cn(
                        "px-3 py-2.5",
                        heatmapBg(
                          c.player.ownership_pct,
                          ranges.ownership.min,
                          ranges.ownership.max,
                        ),
                      )}
                    >
                      {c.player.ownership_pct.toFixed(1)}%
                    </td>

                    {/* Factors — stacked CSS bars */}
                    <td className="px-3 py-2.5">
                      <FactorBars candidate={c} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Differential Captains */}
      {differentials.length > 0 && (
        <div className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Zap className="h-5 w-5 text-amber-500" />
              Differential Captains
            </h2>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Under 10% ownership but in the top 25 by captain score &mdash;
              high risk, high reward
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {differentials.map((c) => (
              <Card
                key={c.player.player_id}
                className="border-l-4 border-l-amber-500"
              >
                <CardContent className="pt-4 pb-3">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="font-medium">{c.player.web_name}</p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {c.player.team_short} &middot;{" "}
                        <Badge
                          className={cn(
                            "text-[10px] px-1.5 py-0",
                            positionColor(c.player.position),
                          )}
                        >
                          {c.player.position}
                        </Badge>{" "}
                        &middot; {formatPrice(c.player.price)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p
                        className={cn(
                          "text-lg font-bold",
                          scoreColor(c.captainScore),
                        )}
                      >
                        {c.captainScore.toFixed(1)}
                      </p>
                      <p className="text-[10px] text-[var(--muted-foreground)]">
                        captain score
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
                    <span>Form {c.player.points_per_game.toFixed(1)}</span>
                    <span>Own {c.player.ownership_pct.toFixed(1)}%</span>
                    {c.player.fdr_next_3 != null && (
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 text-[10px] font-medium",
                          fdrClass(c.player.fdr_next_3),
                        )}
                      >
                        FDR {c.player.fdr_next_3.toFixed(1)}
                      </span>
                    )}
                  </div>
                  <div className="mt-2">
                    <FactorBars candidate={c} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function TopPickHero({ candidate }: { candidate: CaptainCandidate }) {
  const c = candidate;
  const xgPer90 =
    c.player.xg != null && c.player.minutes > 0
      ? ((c.player.xg / c.player.minutes) * 90).toFixed(2)
      : null;

  return (
    <Card className="border-l-4 border-l-amber-500 bg-gradient-to-r from-amber-50/50 to-transparent dark:from-amber-950/20 dark:to-transparent">
      <CardContent className="pt-5 pb-5">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Crown className="h-5 w-5 text-amber-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                Top Captain Pick
              </span>
            </div>
            <p className="text-2xl font-bold">{c.player.web_name}</p>
            <p className="text-sm text-[var(--muted-foreground)]">
              {c.player.team_short} &middot;{" "}
              <Badge
                className={cn(
                  "text-xs px-1.5 py-0",
                  positionColor(c.player.position),
                )}
              >
                {c.player.position}
              </Badge>{" "}
              &middot; {formatPrice(c.player.price)}
            </p>
          </div>
          <div className="text-right">
            <p
              className={cn(
                "text-3xl font-bold",
                scoreColor(c.captainScore),
              )}
            >
              {c.captainScore.toFixed(1)}
            </p>
            <p className="text-xs text-[var(--muted-foreground)]">
              captain score
            </p>
          </div>
        </div>

        {/* Score breakdown pills */}
        <div className="flex flex-wrap gap-3 mt-4">
          <BreakdownPill
            icon={<TrendingUp className="h-3.5 w-3.5" />}
            label="Form"
            value={c.player.points_per_game.toFixed(1)}
            subtext="ppg"
            norm={c.formNorm}
          />
          <BreakdownPill
            icon={<Target className="h-3.5 w-3.5" />}
            label="xG/90"
            value={xgPer90 ?? "-"}
            norm={c.xgPerNinetyNorm}
          />
          <BreakdownPill
            label="Fixtures"
            value={c.player.fdr_next_3?.toFixed(1) ?? "-"}
            subtext="FDR"
            norm={c.fixtureNorm}
          />
          <BreakdownPill
            label="Points"
            value={String(c.player.total_points)}
            norm={c.pointsNorm}
          />
          <BreakdownPill
            label="Ownership"
            value={`${c.player.ownership_pct.toFixed(1)}%`}
            norm={c.ownershipNorm}
          />
        </div>

        {/* Factor bar */}
        <div className="mt-4" style={{ maxWidth: 320 }}>
          <FactorBars candidate={c} tall />
        </div>
      </CardContent>
    </Card>
  );
}

function BreakdownPill({
  icon,
  label,
  value,
  subtext,
  norm,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
  subtext?: string;
  norm: number;
}) {
  const bgClass =
    norm >= 70
      ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
      : norm <= 30
        ? "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
        : "bg-[var(--muted)] border-[var(--border)]";

  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-1.5 text-center min-w-[80px]",
        bgClass,
      )}
    >
      <div className="flex items-center justify-center gap-1 text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider mb-0.5">
        {icon}
        {label}
      </div>
      <p className="text-sm font-bold">{value}</p>
      {subtext && (
        <p className="text-[10px] text-[var(--muted-foreground)]">{subtext}</p>
      )}
    </div>
  );
}

function FactorBars({
  candidate,
  tall = false,
}: {
  candidate: CaptainCandidate;
  tall?: boolean;
}) {
  const total =
    candidate.formNorm * WEIGHTS.form +
    candidate.xgPerNinetyNorm * WEIGHTS.xg +
    candidate.fixtureNorm * WEIGHTS.fixture +
    candidate.pointsNorm * WEIGHTS.points +
    candidate.ownershipNorm * WEIGHTS.ownership;

  const segments = FACTOR_COLORS.map((f) => {
    const raw = (candidate[f.key as keyof CaptainCandidate] as number) *
      WEIGHTS[
        f.key === "formNorm"
          ? "form"
          : f.key === "xgPerNinetyNorm"
            ? "xg"
            : f.key === "fixtureNorm"
              ? "fixture"
              : f.key === "pointsNorm"
                ? "points"
                : "ownership"
      ];
    const pct = total > 0 ? (raw / total) * 100 : 20;
    return { ...f, pct };
  });

  return (
    <div>
      <div
        className={cn(
          "flex rounded-full overflow-hidden",
          tall ? "h-3" : "h-2",
        )}
        title={segments.map((s) => `${s.label}: ${s.pct.toFixed(0)}%`).join(", ")}
      >
        {segments.map((s) => (
          <div
            key={s.key}
            className="transition-all"
            style={{
              width: `${s.pct}%`,
              backgroundColor: s.color,
              minWidth: s.pct > 0 ? 2 : 0,
            }}
          />
        ))}
      </div>
      {tall && (
        <div className="flex gap-3 mt-1.5 flex-wrap">
          {segments.map((s) => (
            <span
              key={s.key}
              className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]"
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: s.color }}
              />
              {s.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
