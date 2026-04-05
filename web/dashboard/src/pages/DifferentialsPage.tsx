import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  LabelList,
  Cell,
} from "recharts";
import { TrendingUp, TrendingDown, Minus, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { PlayerDashboard, PlayerHistory } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import {
  cn,
  formatPrice,
  positionColor,
  scoreColor,
  fdrClass,
  POS_CHART_COLORS,
  TOOLTIP_STYLE,
} from "@/lib/utils";

const POSITIONS = ["All", "GKP", "DEF", "MID", "FWD"] as const;

type Position = (typeof POSITIONS)[number];

interface DifferentialPlayer extends PlayerDashboard {
  differential_score: number;
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

function truncateSentences(text: string, max: number): string {
  const sentences = text.match(/[^.!?]+[.!?]+/g);
  if (!sentences) return text.slice(0, 120);
  return sentences.slice(0, max).join(" ").trim();
}

/** Tiny inline sparkline rendered as an SVG polyline. */
function MiniSparkline({
  values,
  width = 100,
  height = 30,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke="var(--chart-1)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Dot on the last point */}
      {(() => {
        const lastX = width;
        const lastY =
          height -
          ((values[values.length - 1] - min) / range) * (height - 4) -
          2;
        return (
          <circle cx={lastX.toFixed(1)} cy={lastY.toFixed(1)} r="2.5" fill="var(--chart-1)" />
        );
      })()}
    </svg>
  );
}

function FormTrendIcon({ trend }: { trend: string | null }) {
  if (trend === "improving")
    return (
      <span className="flex items-center gap-1 text-green-600 dark:text-green-400 text-xs font-medium">
        <TrendingUp className="h-3.5 w-3.5" /> Improving
      </span>
    );
  if (trend === "declining")
    return (
      <span className="flex items-center gap-1 text-red-500 dark:text-red-400 text-xs font-medium">
        <TrendingDown className="h-3.5 w-3.5" /> Declining
      </span>
    );
  return (
    <span className="flex items-center gap-1 text-[var(--muted-foreground)] text-xs font-medium">
      <Minus className="h-3.5 w-3.5" /> Stable
    </span>
  );
}

function FdrBadges({ fdr }: { fdr: number | null }) {
  if (fdr == null) return null;
  // Approximate individual fixture difficulties from the average
  const badges = [Math.max(1, Math.round(fdr - 0.3)), Math.round(fdr), Math.min(5, Math.round(fdr + 0.3))];
  return (
    <div className="flex gap-1">
      {badges.map((d, i) => (
        <span
          key={i}
          className={cn(
            "inline-flex items-center justify-center w-6 h-5 rounded text-[10px] font-bold",
            fdrClass(d),
          )}
        >
          {d}
        </span>
      ))}
    </div>
  );
}

// Custom label renderer for top-5 dots on the scatter plot
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderTopLabel(props: any) {
  const { x, y, value } = props as { x: number; y: number; value: string };
  if (!value) return null;
  return (
    <text
      x={x}
      y={y - 10}
      textAnchor="middle"
      fontSize={11}
      fontWeight={600}
      fill="var(--foreground)"
    >
      {value}
    </text>
  );
}

export function DifferentialsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const posFilter = (searchParams.get("pos") ?? "All") as Position;

  const {
    data: players,
    loading: loadingPlayers,
    error: errorPlayers,
  } = useApi(api.players, [] as PlayerDashboard[]);

  const {
    data: history,
    loading: loadingHistory,
    error: errorHistory,
  } = useApi(api.history, [] as PlayerHistory[]);

  const loading = loadingPlayers || loadingHistory;
  const error = errorPlayers || errorHistory;

  // Filter to low-ownership players and compute differential_score
  const differentials: DifferentialPlayer[] = useMemo(() => {
    return players
      .filter((p) => p.ownership_pct < 15)
      .filter((p) => posFilter === "All" || p.position === posFilter)
      .map((p) => ({
        ...p,
        differential_score: p.fpl_score * (1 - p.ownership_pct / 100),
      }))
      .sort((a, b) => b.differential_score - a.differential_score);
  }, [players, posFilter]);

  // Chart data: each point needs ownership_pct, fpl_score, position, label (for top 5)
  const { chartData, medianOwnership, medianScore } = useMemo(() => {
    if (differentials.length === 0)
      return { chartData: [], medianOwnership: 0, medianScore: 0 };

    const top5Ids = new Set(differentials.slice(0, 5).map((p) => p.player_id));
    const medOwn = median(differentials.map((p) => p.ownership_pct));
    const medScr = median(differentials.map((p) => p.fpl_score));

    const data = differentials.map((p) => ({
      ownership_pct: p.ownership_pct,
      fpl_score: p.fpl_score,
      position: p.position,
      web_name: p.web_name,
      label: top5Ids.has(p.player_id) ? p.web_name : "",
      differential_score: p.differential_score,
    }));

    return { chartData: data, medianOwnership: medOwn, medianScore: medScr };
  }, [differentials]);

  // Build a map of player_id -> last N gameweeks of fpl_score from history
  const sparklineMap = useMemo(() => {
    const map = new Map<number, number[]>();
    if (history.length === 0) return map;

    const grouped = new Map<number, { gw: number; score: number }[]>();
    for (const h of history) {
      if (!grouped.has(h.player_id)) grouped.set(h.player_id, []);
      grouped.get(h.player_id)!.push({ gw: h.gameweek, score: h.fpl_score });
    }
    for (const [pid, rows] of grouped) {
      rows.sort((a, b) => a.gw - b.gw);
      map.set(
        pid,
        rows.slice(-10).map((r) => r.score),
      );
    }
    return map;
  }, [history]);

  const top12 = differentials.slice(0, 12);

  function setPosition(pos: Position) {
    const next = new URLSearchParams(searchParams);
    if (pos === "All") next.delete("pos");
    else next.set("pos", pos);
    setSearchParams(next, { replace: true });
  }

  if (loading) return <TableSkeleton rows={8} />;
  if (error) return <ErrorCard message={error} />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-amber-500" />
          Differential Radar
        </h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          Low ownership, high value &mdash; the players your rivals don&apos;t
          have
        </p>
      </div>

      {/* Position filter */}
      <div className="flex gap-1.5">
        {POSITIONS.map((pos) => (
          <button
            key={pos}
            onClick={() => setPosition(pos)}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              posFilter === pos
                ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                : "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--border)]",
            )}
          >
            {pos}
          </button>
        ))}
      </div>

      {/* Scatter chart */}
      {differentials.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Ownership vs FPL Score
              <span className="ml-2 text-xs font-normal text-[var(--muted-foreground)]">
                ({differentials.length} players under 15% ownership)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={400}>
              <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border)"
                  opacity={0.5}
                />
                <XAxis
                  type="number"
                  dataKey="ownership_pct"
                  name="Ownership"
                  unit="%"
                  domain={[0, 15]}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  label={{
                    value: "Ownership %",
                    position: "insideBottom",
                    offset: -10,
                    fontSize: 12,
                    fill: "var(--muted-foreground)",
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="fpl_score"
                  name="FPL Score"
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  label={{
                    value: "FPL Score",
                    angle: -90,
                    position: "insideLeft",
                    fontSize: 12,
                    fill: "var(--muted-foreground)",
                  }}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  formatter={(value: unknown, name: unknown) => {
                    const v = Number(value);
                    const n = String(name);
                    if (n === "Ownership") return [`${v.toFixed(1)}%`, n];
                    if (n === "FPL Score") return [v.toFixed(1), n];
                    return [v, n];
                  }}
                  labelFormatter={(_: unknown, payload: ReadonlyArray<{ payload?: { web_name?: string } }>) =>
                    payload?.[0]?.payload?.web_name ?? ""
                  }
                />
                {/* Reference lines at medians */}
                <ReferenceLine
                  x={medianOwnership}
                  stroke="var(--muted-foreground)"
                  strokeDasharray="4 4"
                  opacity={0.5}
                />
                <ReferenceLine
                  y={medianScore}
                  stroke="var(--muted-foreground)"
                  strokeDasharray="4 4"
                  opacity={0.5}
                />
                <Scatter data={chartData} shape="circle">
                  {chartData.map((entry, idx) => (
                    <Cell
                      key={idx}
                      fill={POS_CHART_COLORS[entry.position] ?? "var(--chart-1)"}
                      fillOpacity={0.75}
                      r={5}
                    />
                  ))}
                  <LabelList dataKey="label" content={renderTopLabel} />
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>

            {/* Quadrant labels */}
            <div className="grid grid-cols-2 gap-2 mt-2 text-[10px] uppercase tracking-wider text-[var(--muted-foreground)] text-center">
              <span>Hidden Gems (low own, high score)</span>
              <span>Rising Stars (higher own, high score)</span>
              <span>Deep Differentials (low own, low score)</span>
              <span>Fading (higher own, low score)</span>
            </div>

            {/* Position legend */}
            <div className="flex gap-4 mt-3 justify-center">
              {(["GKP", "DEF", "MID", "FWD"] as const).map((pos) => (
                <div key={pos} className="flex items-center gap-1.5 text-xs">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: POS_CHART_COLORS[pos] }}
                  />
                  <span>{pos}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Top 12 differential cards */}
      {top12.length > 0 && (
        <>
          <h2 className="text-lg font-semibold">
            Top Differentials
            <span className="ml-2 text-sm font-normal text-[var(--muted-foreground)]">
              by differential score
            </span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {top12.map((p) => {
              const posCol = positionColor(p.position);
              const borderColor: Record<string, string> = {
                GKP: "border-l-amber-500",
                DEF: "border-l-blue-500",
                MID: "border-l-green-500",
                FWD: "border-l-red-500",
              };
              const sparkValues = sparklineMap.get(p.player_id);

              return (
                <Card
                  key={p.player_id}
                  className={cn(
                    "border-l-4 transition-shadow hover:shadow-md",
                    borderColor[p.position] ?? "border-l-gray-400",
                  )}
                >
                  <CardContent className="pt-4 space-y-3">
                    {/* Name row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">
                          {p.web_name}
                        </span>
                        <span className="text-xs text-[var(--muted-foreground)]">
                          {p.team_short}
                        </span>
                        <Badge className={cn(posCol, "text-[10px]")}>
                          {p.position}
                        </Badge>
                      </div>
                    </div>

                    {/* Differential score */}
                    <div className="flex items-baseline gap-4">
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
                          Diff Score
                        </p>
                        <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                          {p.differential_score.toFixed(1)}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
                          FPL Score
                        </p>
                        <p className={cn("text-lg font-semibold", scoreColor(p.fpl_score))}>
                          {p.fpl_score.toFixed(1)}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
                          Ownership
                        </p>
                        <p className="text-lg font-semibold">
                          {p.ownership_pct.toFixed(1)}%
                        </p>
                      </div>
                    </div>

                    {/* Form trend + price */}
                    <div className="flex items-center justify-between">
                      <FormTrendIcon trend={p.form_trend} />
                      <span className="text-xs text-[var(--muted-foreground)]">
                        {formatPrice(p.price)}
                      </span>
                    </div>

                    {/* FDR badges */}
                    {p.fdr_next_3 != null && (
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
                          Next 3 FDR
                        </span>
                        <FdrBadges fdr={p.fdr_next_3} />
                      </div>
                    )}

                    {/* Best gameweeks */}
                    {p.best_gameweeks && p.best_gameweeks.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
                          Best GWs
                        </span>
                        {p.best_gameweeks.map((gw) => (
                          <Badge
                            key={gw}
                            className="bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 text-[10px]"
                          >
                            GW{gw}
                          </Badge>
                        ))}
                      </div>
                    )}

                    {/* Sparkline */}
                    {sparkValues && sparkValues.length >= 2 && (
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
                          Trend
                        </span>
                        <MiniSparkline values={sparkValues} />
                      </div>
                    )}

                    {/* LLM summary */}
                    {p.llm_summary && (
                      <p className="text-xs text-[var(--muted-foreground)] leading-relaxed line-clamp-3">
                        {truncateSentences(p.llm_summary, 2)}
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {differentials.length === 0 && (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <p className="text-lg">No differentials found</p>
          <p className="text-sm mt-1">
            No players under 15% ownership match the current filter
          </p>
        </div>
      )}
    </div>
  );
}
