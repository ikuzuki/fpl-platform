import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Search } from "lucide-react";
import { MetricIcons } from "@/components/icons/FplIcons";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { PlayerHistory } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import {
  cn,
  formatPrice,
  positionColor,
  scoreColor,
  CHART_COLORS,
  TOOLTIP_STYLE,
} from "@/lib/utils";

type Metric = "fpl_score" | "price" | "ownership_pct" | "form" | "points_per_million";

const METRICS: { key: Metric; label: string; format: (v: number) => string }[] = [
  { key: "fpl_score", label: "FPL Score", format: (v) => v.toFixed(1) },
  { key: "price", label: "Price", format: (v) => formatPrice(v) },
  { key: "ownership_pct", label: "Ownership", format: (v) => `${v.toFixed(1)}%` },
  { key: "form", label: "Form", format: (v) => v.toFixed(1) },
  { key: "points_per_million", label: "Pts/M", format: (v) => v.toFixed(1) },
];

export function TrendsPage() {
  const { data, loading, error } = useApi(() => api.history(), [] as PlayerHistory[]);

  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("q") ?? "";
  const metric = (searchParams.get("metric") as Metric) ?? "fpl_score";

  const selectedParam = searchParams.get("ids");
  const selected = useMemo(
    () => (selectedParam ? selectedParam.split(",").map(Number).filter(Boolean) : []),
    [selectedParam],
  );

  const setSearch = (q: string) => {
    const next = new URLSearchParams(searchParams);
    if (q) next.set("q", q);
    else next.delete("q");
    setSearchParams(next, { replace: true });
  };

  const setMetric = (m: Metric) => {
    const next = new URLSearchParams(searchParams);
    next.set("metric", m);
    setSearchParams(next, { replace: true });
  };

  const setSelected = (updater: (prev: number[]) => number[]) => {
    const next = new URLSearchParams(searchParams);
    const updated = updater(selected);
    if (updated.length > 0) next.set("ids", updated.join(","));
    else next.delete("ids");
    setSearchParams(next, { replace: true });
  };

  const gameweeks = useMemo(
    () => [...new Set(data.map((r) => r.gameweek))].sort((a, b) => a - b),
    [data],
  );

  const latestGw = gameweeks[gameweeks.length - 1];
  const players = useMemo(() => {
    return data
      .filter((r) => r.gameweek === latestGw)
      .sort((a, b) => a.fpl_score_rank - b.fpl_score_rank);
  }, [data, latestGw]);

  const filteredPlayers = useMemo(() => {
    if (!search) return players.slice(0, 30);
    const q = search.toLowerCase();
    return players.filter(
      (p) =>
        p.web_name.toLowerCase().includes(q) ||
        p.team_short.toLowerCase().includes(q),
    );
  }, [players, search]);

  const chartData = useMemo(() => {
    if (selected.length === 0) return [];
    return gameweeks.map((gw) => {
      const point: Record<string, number | string> = { gameweek: `GW${gw}` };
      selected.forEach((pid) => {
        const row = data.find((r) => r.player_id === pid && r.gameweek === gw);
        const player = players.find((p) => p.player_id === pid);
        const key = player?.web_name ?? `Player ${pid}`;
        point[key] = row?.[metric] ?? 0;
      });
      return point;
    });
  }, [data, gameweeks, selected, metric, players]);

  const selectedNames = selected.map(
    (pid) => players.find((p) => p.player_id === pid)?.web_name ?? "",
  );

  const movers = useMemo(() => {
    if (gameweeks.length < 2) return { risers: [], fallers: [] };
    const firstGw = gameweeks[0];
    const lastGw = gameweeks[gameweeks.length - 1];

    const deltas = players
      .map((p) => {
        const first = data.find((r) => r.player_id === p.player_id && r.gameweek === firstGw);
        const last = data.find((r) => r.player_id === p.player_id && r.gameweek === lastGw);
        if (!first || !last) return null;
        return {
          ...p,
          delta: last.fpl_score - first.fpl_score,
          priceDelta: last.price - first.price,
          ownershipDelta: last.ownership_pct - first.ownership_pct,
        };
      })
      .filter((d) => d !== null);

    return {
      risers: deltas.sort((a, b) => b.delta - a.delta).slice(0, 5),
      fallers: deltas.sort((a, b) => a.delta - b.delta).slice(0, 5),
    };
  }, [data, gameweeks, players]);

  if (loading) return <TableSkeleton rows={10} />;
  if (error) return <ErrorCard message={error} />;

  if (gameweeks.length === 0) {
    return (
      <div className="text-center py-12 text-[var(--muted-foreground)]">
        <p className="text-lg">No history data available yet</p>
        <p className="text-sm mt-1">
          Run the pipeline for at least one gameweek to start tracking trends
        </p>
      </div>
    );
  }

  const metricConfig = METRICS.find((m) => m.key === metric)!;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Player Trends</h1>
        <span className="text-sm text-[var(--muted-foreground)]">
          {gameweeks.length} gameweeks &middot; GW{gameweeks[0]}-GW{gameweeks[gameweeks.length - 1]}
        </span>
      </div>

      {/* Movers cards */}
      {gameweeks.length >= 2 && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="border-l-4 border-l-green-500">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <MetricIcons.PriceUp size={16} />
                Biggest Risers (FPL Score)
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {movers.risers.map((p) => (
                <div
                  key={p.player_id}
                  className="flex items-center justify-between py-1.5 border-b border-[var(--border)] last:border-b-0 cursor-pointer hover:bg-[var(--muted)]/50 rounded px-1"
                  role="button"
                  tabIndex={0}
                  onClick={() =>
                    setSelected((prev) =>
                      prev.includes(p.player_id)
                        ? prev.filter((id) => id !== p.player_id)
                        : [...prev.slice(-4), p.player_id],
                    )
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected((prev) =>
                        prev.includes(p.player_id)
                          ? prev.filter((id) => id !== p.player_id)
                          : [...prev.slice(-4), p.player_id],
                      );
                    }
                  }}
                >
                  <div className="flex items-center gap-2">
                    <Badge className={cn(positionColor(p.position), "text-[10px]")}>{p.position}</Badge>
                    <span className="text-sm font-medium">{p.web_name}</span>
                    <span className="text-xs text-[var(--muted-foreground)]">{p.team_short}</span>
                  </div>
                  <span className="text-sm font-bold text-green-600 dark:text-green-400">
                    +{p.delta.toFixed(1)}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-red-500">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <MetricIcons.PriceDown size={16} />
                Biggest Fallers (FPL Score)
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {movers.fallers.map((p) => (
                <div
                  key={p.player_id}
                  className="flex items-center justify-between py-1.5 border-b border-[var(--border)] last:border-b-0 cursor-pointer hover:bg-[var(--muted)]/50 rounded px-1"
                  role="button"
                  tabIndex={0}
                  onClick={() =>
                    setSelected((prev) =>
                      prev.includes(p.player_id)
                        ? prev.filter((id) => id !== p.player_id)
                        : [...prev.slice(-4), p.player_id],
                    )
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected((prev) =>
                        prev.includes(p.player_id)
                          ? prev.filter((id) => id !== p.player_id)
                          : [...prev.slice(-4), p.player_id],
                      );
                    }
                  }}
                >
                  <div className="flex items-center gap-2">
                    <Badge className={cn(positionColor(p.position), "text-[10px]")}>{p.position}</Badge>
                    <span className="text-sm font-medium">{p.web_name}</span>
                    <span className="text-xs text-[var(--muted-foreground)]">{p.team_short}</span>
                  </div>
                  <span className="text-sm font-bold text-red-500 dark:text-red-400">
                    {p.delta.toFixed(1)}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Chart + player picker */}
      <div className="grid gap-4 md:grid-cols-12">
        {/* Player picker */}
        <div className="md:col-span-3">
          <Card className="h-full">
            <CardContent className="pt-4">
              <div className="relative mb-3">
                <Search className="absolute left-2.5 top-2 h-4 w-4 text-[var(--muted-foreground)]" />
                <label htmlFor="trends-search" className="sr-only">Search players</label>
                <input
                  id="trends-search"
                  type="text"
                  placeholder="Search player..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] pl-8 pr-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>
              <p className="text-[10px] text-[var(--muted-foreground)] mb-2 uppercase tracking-wider">
                Click to compare (max 5)
              </p>
              <div className="space-y-0.5 max-h-[400px] overflow-y-auto">
                {filteredPlayers.map((p) => {
                  const isSelected = selected.includes(p.player_id);
                  const colorIdx = selected.indexOf(p.player_id);
                  return (
                    <button
                      key={p.player_id}
                      onClick={() =>
                        setSelected((prev) =>
                          isSelected
                            ? prev.filter((id) => id !== p.player_id)
                            : prev.length >= 5
                              ? prev
                              : [...prev, p.player_id],
                        )
                      }
                      className={cn(
                        "w-full flex items-center justify-between px-2 py-1.5 rounded text-left text-sm transition-colors",
                        isSelected ? "bg-[var(--accent)]/10 font-medium" : "hover:bg-[var(--muted)]",
                      )}
                      aria-pressed={isSelected}
                    >
                      <div className="flex items-center gap-2">
                        {isSelected && (
                          <div
                            className="w-2.5 h-2.5 rounded-full"
                            style={{ backgroundColor: CHART_COLORS[colorIdx % CHART_COLORS.length] }}
                          />
                        )}
                        <span>{p.web_name}</span>
                        <span className="text-[10px] text-[var(--muted-foreground)]">{p.team_short}</span>
                      </div>
                      <span className={cn("text-xs font-mono", scoreColor(p.fpl_score))}>
                        {p.fpl_score.toFixed(1)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Chart */}
        <div className="md:col-span-9">
          <Card className="h-full">
            <CardHeader>
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                <CardTitle>
                  {selected.length === 0 ? "Select players to compare" : `${metricConfig.label} over time`}
                </CardTitle>
                <div className="flex gap-1 flex-wrap" role="group" aria-label="Select metric">
                  {METRICS.map((m) => (
                    <button
                      key={m.key}
                      onClick={() => setMetric(m.key)}
                      className={cn(
                        "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                        metric === m.key
                          ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                          : "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--border)]",
                      )}
                      aria-pressed={metric === m.key}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {selected.length === 0 ? (
                <div className="flex items-center justify-center h-[300px] text-[var(--muted-foreground)]">
                  <p className="text-sm">Pick players from the list or click a riser/faller to start</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={340}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
                    <XAxis dataKey="gameweek" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} domain={["auto", "auto"]} />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      formatter={(value) => metricConfig.format(Number(value))}
                    />
                    {selectedNames.map((name, i) => (
                      <Line
                        key={name}
                        type="monotone"
                        dataKey={name}
                        stroke={CHART_COLORS[i % CHART_COLORS.length]}
                        strokeWidth={2.5}
                        dot={{ r: 4, fill: CHART_COLORS[i % CHART_COLORS.length] }}
                        activeDot={{ r: 6 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              )}

              {/* Sentiment Timeline */}
              {selected.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-2">
                    Sentiment Timeline
                  </p>
                  {selected.map((pid, i) => {
                    const p = players.find((pl) => pl.player_id === pid);
                    if (!p) return null;
                    return (
                      <div key={pid} className="flex items-center gap-2 mb-1">
                        <span className="text-xs w-20 truncate" style={{ color: CHART_COLORS[i % CHART_COLORS.length] }}>
                          {p.web_name}
                        </span>
                        <div className="flex gap-0.5">
                          {gameweeks.map((gw) => {
                            const row = data.find((r) => r.player_id === pid && r.gameweek === gw);
                            const score = row?.sentiment_score;
                            let bg = "bg-gray-200 dark:bg-gray-700";
                            if (score != null) {
                              if (score > 0.3) bg = "bg-green-400 dark:bg-green-600";
                              else if (score > 0) bg = "bg-green-200 dark:bg-green-800";
                              else if (score < -0.3) bg = "bg-red-400 dark:bg-red-600";
                              else if (score < 0) bg = "bg-red-200 dark:bg-red-800";
                            }
                            return (
                              <div
                                key={gw}
                                className={cn("w-8 h-4 rounded-sm", bg)}
                                title={`GW${gw}: ${score?.toFixed(2) ?? "n/a"}`}
                              />
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                  <div className="flex gap-0.5 ml-[88px] mt-1">
                    {gameweeks.map((gw) => (
                      <div key={gw} className="w-8 text-center text-[9px] text-[var(--muted-foreground)]">{gw}</div>
                    ))}
                  </div>
                </div>
              )}

              {/* Selected player chips */}
              {selected.length > 0 && (
                <div className="flex gap-2 mt-3 flex-wrap">
                  {selected.map((pid, i) => {
                    const p = players.find((pl) => pl.player_id === pid);
                    if (!p) return null;
                    return (
                      <button
                        key={pid}
                        onClick={() => setSelected((prev) => prev.filter((id) => id !== pid))}
                        className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium bg-[var(--muted)] hover:bg-[var(--border)] transition-colors"
                      >
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                        {p.web_name}
                        <span className="text-[var(--muted-foreground)] ml-1">&times;</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
