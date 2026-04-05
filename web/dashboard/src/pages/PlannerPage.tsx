import { useMemo, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
} from "recharts";
import {
  ArrowRightLeft,
  Search,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  ShieldCheck,
  Zap,
  Calendar,
} from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { PlayerDashboard, PlayerHistory } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import {
  cn,
  formatPrice,
  formatNumber,
  positionColor,
  scoreColor,
  fdrClass,
  SCORE_COMPONENTS,
  TOOLTIP_STYLE,
} from "@/lib/utils";

type Position = "All" | "GKP" | "DEF" | "MID" | "FWD";

const POSITIONS: Position[] = ["All", "GKP", "DEF", "MID", "FWD"];

interface ComparisonRow {
  label: string;
  sellValue: string;
  buyValue: string;
  sellRaw: number;
  buyRaw: number;
  higherIsBetter: boolean;
}

function trendIcon(trend: string | null) {
  if (trend === "rising")
    return <TrendingUp className="h-3.5 w-3.5 text-green-500 inline ml-1" />;
  if (trend === "falling")
    return <TrendingDown className="h-3.5 w-3.5 text-red-500 inline ml-1" />;
  return <Minus className="h-3.5 w-3.5 text-[var(--muted-foreground)] inline ml-1" />;
}

function betterClass(isBetter: boolean, isWorse: boolean): string {
  if (isBetter) return "text-green-600 dark:text-green-400 font-semibold";
  if (isWorse) return "text-red-500 dark:text-red-400";
  return "";
}

export function PlannerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    data: players,
    loading: playersLoading,
    error: playersError,
  } = useApi(api.players, []);
  const {
    data: history,
    loading: historyLoading,
    error: historyError,
  } = useApi(api.history, []);

  const loading = playersLoading || historyLoading;
  const error = playersError || historyError;

  const sellId = searchParams.get("sell") ? Number(searchParams.get("sell")) : null;
  const buyId = searchParams.get("buy") ? Number(searchParams.get("buy")) : null;

  const [sellSearch, setSellSearch] = useState("");
  const [buySearch, setBuySearch] = useState("");
  const [posFilter, setPosFilter] = useState<Position>("All");

  const sellPlayer = useMemo(
    () => (sellId ? players.find((p) => p.player_id === sellId) ?? null : null),
    [players, sellId],
  );
  const buyPlayer = useMemo(
    () => (buyId ? players.find((p) => p.player_id === buyId) ?? null : null),
    [players, buyId],
  );

  // When sell player is selected, auto-filter buy panel to same position
  const buyPositionFilter = sellPlayer ? (sellPlayer.position as Position) : posFilter;

  const filteredSell = useMemo(() => {
    let list = players;
    if (posFilter !== "All") list = list.filter((p) => p.position === posFilter);
    if (sellSearch.trim()) {
      const q = sellSearch.toLowerCase();
      list = list.filter(
        (p) =>
          p.web_name.toLowerCase().includes(q) ||
          p.full_name.toLowerCase().includes(q) ||
          p.team_short.toLowerCase().includes(q),
      );
    }
    return list.sort((a, b) => b.fpl_score - a.fpl_score).slice(0, 50);
  }, [players, posFilter, sellSearch]);

  const filteredBuy = useMemo(() => {
    let list = players;
    const effectivePos = buyPositionFilter;
    if (effectivePos !== "All") list = list.filter((p) => p.position === effectivePos);
    if (buySearch.trim()) {
      const q = buySearch.toLowerCase();
      list = list.filter(
        (p) =>
          p.web_name.toLowerCase().includes(q) ||
          p.full_name.toLowerCase().includes(q) ||
          p.team_short.toLowerCase().includes(q),
      );
    }
    // Exclude the sell player from the buy panel
    if (sellId) list = list.filter((p) => p.player_id !== sellId);
    return list.sort((a, b) => b.fpl_score - a.fpl_score).slice(0, 50);
  }, [players, buyPositionFilter, buySearch, sellId]);

  const setSell = useCallback(
    (id: number) => {
      const params = new URLSearchParams(searchParams);
      params.set("sell", String(id));
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setBuy = useCallback(
    (id: number) => {
      const params = new URLSearchParams(searchParams);
      params.set("buy", String(id));
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  // History data for sparklines
  const sellHistory = useMemo(
    () =>
      sellId
        ? history
            .filter((h) => h.player_id === sellId)
            .sort((a, b) => a.gameweek - b.gameweek)
        : [],
    [history, sellId],
  );
  const buyHistory = useMemo(
    () =>
      buyId
        ? history
            .filter((h) => h.player_id === buyId)
            .sort((a, b) => a.gameweek - b.gameweek)
        : [],
    [history, buyId],
  );

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Transfer Planner</h1>
        <p className="text-[var(--muted-foreground)]">
          Compare players side-by-side and simulate transfers
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Transfer Planner</h1>
        <ErrorCard message={error} />
      </div>
    );
  }

  const bothSelected = sellPlayer && buyPlayer;

  // Build comparison rows
  const comparisonRows: ComparisonRow[] = bothSelected
    ? [
        {
          label: "FPL Score",
          sellValue: sellPlayer.fpl_score.toFixed(1),
          buyValue: buyPlayer.fpl_score.toFixed(1),
          sellRaw: sellPlayer.fpl_score,
          buyRaw: buyPlayer.fpl_score,
          higherIsBetter: true,
        },
        {
          label: "Form",
          sellValue: sellPlayer.form.toFixed(1),
          buyValue: buyPlayer.form.toFixed(1),
          sellRaw: sellPlayer.form,
          buyRaw: buyPlayer.form,
          higherIsBetter: true,
        },
        {
          label: "Price",
          sellValue: formatPrice(sellPlayer.price),
          buyValue: formatPrice(buyPlayer.price),
          sellRaw: sellPlayer.price,
          buyRaw: buyPlayer.price,
          higherIsBetter: false,
        },
        {
          label: "Total Points",
          sellValue: String(sellPlayer.total_points),
          buyValue: String(buyPlayer.total_points),
          sellRaw: sellPlayer.total_points,
          buyRaw: buyPlayer.total_points,
          higherIsBetter: true,
        },
        {
          label: "Pts / Million",
          sellValue: sellPlayer.points_per_million.toFixed(1),
          buyValue: buyPlayer.points_per_million.toFixed(1),
          sellRaw: sellPlayer.points_per_million,
          buyRaw: buyPlayer.points_per_million,
          higherIsBetter: true,
        },
        {
          label: "xG / xA",
          sellValue: `${sellPlayer.xg?.toFixed(1) ?? "-"} / ${sellPlayer.xa?.toFixed(1) ?? "-"}`,
          buyValue: `${buyPlayer.xg?.toFixed(1) ?? "-"} / ${buyPlayer.xa?.toFixed(1) ?? "-"}`,
          sellRaw: (sellPlayer.xg ?? 0) + (sellPlayer.xa ?? 0),
          buyRaw: (buyPlayer.xg ?? 0) + (buyPlayer.xa ?? 0),
          higherIsBetter: true,
        },
        {
          label: "ICT Index",
          sellValue: sellPlayer.ict_index.toFixed(1),
          buyValue: buyPlayer.ict_index.toFixed(1),
          sellRaw: sellPlayer.ict_index,
          buyRaw: buyPlayer.ict_index,
          higherIsBetter: true,
        },
        {
          label: "Injury Risk",
          sellValue: sellPlayer.injury_risk != null ? `${sellPlayer.injury_risk}/10` : "-",
          buyValue: buyPlayer.injury_risk != null ? `${buyPlayer.injury_risk}/10` : "-",
          sellRaw: sellPlayer.injury_risk ?? 0,
          buyRaw: buyPlayer.injury_risk ?? 0,
          higherIsBetter: false,
        },
        {
          label: "FDR Next 3",
          sellValue: sellPlayer.fdr_next_3?.toFixed(1) ?? "-",
          buyValue: buyPlayer.fdr_next_3?.toFixed(1) ?? "-",
          sellRaw: sellPlayer.fdr_next_3 ?? 3,
          buyRaw: buyPlayer.fdr_next_3 ?? 3,
          higherIsBetter: false,
        },
        {
          label: "Ownership",
          sellValue: `${sellPlayer.ownership_pct.toFixed(1)}%`,
          buyValue: `${buyPlayer.ownership_pct.toFixed(1)}%`,
          sellRaw: sellPlayer.ownership_pct,
          buyRaw: buyPlayer.ownership_pct,
          higherIsBetter: true,
        },
        {
          label: "Net Transfers",
          sellValue: formatNumber(sellPlayer.net_transfers),
          buyValue: formatNumber(buyPlayer.net_transfers),
          sellRaw: sellPlayer.net_transfers,
          buyRaw: buyPlayer.net_transfers,
          higherIsBetter: true,
        },
        {
          label: "Sentiment",
          sellValue: sellPlayer.sentiment_label ?? "-",
          buyValue: buyPlayer.sentiment_label ?? "-",
          sellRaw: sellPlayer.sentiment_score ?? 0,
          buyRaw: buyPlayer.sentiment_score ?? 0,
          higherIsBetter: true,
        },
      ]
    : [];

  // Budget impact
  const priceDelta = bothSelected ? sellPlayer.price - buyPlayer.price : 0;

  // Verdict
  const verdictText = bothSelected ? buildVerdict(sellPlayer, buyPlayer) : null;

  // Score pyramid data
  const pyramidData = bothSelected
    ? SCORE_COMPONENTS.map((comp) => ({
        label: comp.label,
        sell: -(
          (sellPlayer[comp.key as keyof PlayerDashboard] as number | null) ?? 0
        ),
        buy: (buyPlayer[comp.key as keyof PlayerDashboard] as number | null) ?? 0,
        color: comp.color,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <ArrowRightLeft className="h-6 w-6 text-[var(--accent)]" />
          <h1 className="text-2xl font-bold">Transfer Planner</h1>
        </div>
        <p className="text-[var(--muted-foreground)] mt-1">
          Compare players side-by-side and simulate transfers
        </p>
      </div>

      {/* Position filter */}
      <div className="flex gap-2">
        {POSITIONS.map((pos) => (
          <button
            key={pos}
            onClick={() => setPosFilter(pos)}
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

      {/* Sell / Buy Panels */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Sell Panel */}
        <Card
          className={cn(
            "transition-colors",
            sellPlayer && "border-red-500/60 border-2",
          )}
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
              Sell
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-[var(--muted-foreground)]" />
              <input
                type="text"
                placeholder="Search player..."
                value={sellSearch}
                onChange={(e) => setSellSearch(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--card)] pl-9 pr-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-red-500/30"
              />
            </div>
            <div className="max-h-60 overflow-y-auto space-y-0.5">
              {filteredSell.map((p) => (
                <button
                  key={p.player_id}
                  onClick={() => setSell(p.player_id)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-all",
                    sellId === p.player_id
                      ? "bg-red-100 dark:bg-red-900/30 border border-red-400"
                      : "hover:bg-[var(--muted)]",
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-medium truncate">{p.web_name}</span>
                    <Badge className={cn(positionColor(p.position), "text-[10px] shrink-0")}>
                      {p.position}
                    </Badge>
                    <span className="text-xs text-[var(--muted-foreground)] shrink-0">
                      {p.team_short}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-2">
                    <span className="text-xs text-[var(--muted-foreground)]">
                      {formatPrice(p.price)}
                    </span>
                    <span className={cn("text-xs font-semibold", scoreColor(p.fpl_score))}>
                      {p.fpl_score.toFixed(0)}
                    </span>
                  </div>
                </button>
              ))}
              {filteredSell.length === 0 && (
                <p className="text-center text-sm text-[var(--muted-foreground)] py-4">
                  No players found
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Buy Panel */}
        <Card
          className={cn(
            "transition-colors",
            buyPlayer && "border-green-500/60 border-2",
          )}
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
              Buy
              {sellPlayer && (
                <Badge className={cn(positionColor(sellPlayer.position), "text-[10px]")}>
                  {sellPlayer.position} only
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-[var(--muted-foreground)]" />
              <input
                type="text"
                placeholder="Search player..."
                value={buySearch}
                onChange={(e) => setBuySearch(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--card)] pl-9 pr-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-green-500/30"
              />
            </div>
            <div className="max-h-60 overflow-y-auto space-y-0.5">
              {filteredBuy.map((p) => (
                <button
                  key={p.player_id}
                  onClick={() => setBuy(p.player_id)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-all",
                    buyId === p.player_id
                      ? "bg-green-100 dark:bg-green-900/30 border border-green-400"
                      : "hover:bg-[var(--muted)]",
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-medium truncate">{p.web_name}</span>
                    <Badge className={cn(positionColor(p.position), "text-[10px] shrink-0")}>
                      {p.position}
                    </Badge>
                    <span className="text-xs text-[var(--muted-foreground)] shrink-0">
                      {p.team_short}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-2">
                    <span className="text-xs text-[var(--muted-foreground)]">
                      {formatPrice(p.price)}
                    </span>
                    <span className={cn("text-xs font-semibold", scoreColor(p.fpl_score))}>
                      {p.fpl_score.toFixed(0)}
                    </span>
                  </div>
                </button>
              ))}
              {filteredBuy.length === 0 && (
                <p className="text-center text-sm text-[var(--muted-foreground)] py-4">
                  No players found
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Comparison Section — only when both selected */}
      {bothSelected && (
        <div className="space-y-4 transition-all">
          {/* Budget Impact */}
          <Card>
            <CardContent className="pt-5">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <div className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
                      Sell
                    </div>
                    <div className="text-lg font-bold text-red-500">
                      {formatPrice(sellPlayer.price)}
                    </div>
                    <div className="text-xs text-[var(--muted-foreground)]">
                      {sellPlayer.web_name}
                    </div>
                  </div>
                  <ArrowRightLeft className="h-5 w-5 text-[var(--muted-foreground)]" />
                  <div className="text-center">
                    <div className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
                      Buy
                    </div>
                    <div className="text-lg font-bold text-green-500">
                      {formatPrice(buyPlayer.price)}
                    </div>
                    <div className="text-xs text-[var(--muted-foreground)]">
                      {buyPlayer.web_name}
                    </div>
                  </div>
                </div>
                <div
                  className={cn(
                    "text-right px-4 py-2 rounded-lg",
                    priceDelta >= 0
                      ? "bg-green-50 dark:bg-green-900/20"
                      : "bg-red-50 dark:bg-red-900/20",
                  )}
                >
                  <div className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
                    Budget change
                  </div>
                  <div
                    className={cn(
                      "text-xl font-bold",
                      priceDelta >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-500 dark:text-red-400",
                    )}
                  >
                    {priceDelta >= 0 ? "+" : "-"}&pound;{Math.abs(priceDelta).toFixed(1)}m
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Side-by-Side Comparison Table */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Head-to-Head</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)]">
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider w-1/3">
                        {sellPlayer.web_name}
                      </th>
                      <th className="text-center px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                        Metric
                      </th>
                      <th className="text-right px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider w-1/3">
                        {buyPlayer.web_name}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonRows.map((row, idx) => {
                      const sellBetter = row.higherIsBetter
                        ? row.sellRaw > row.buyRaw
                        : row.sellRaw < row.buyRaw;
                      const buyBetter = row.higherIsBetter
                        ? row.buyRaw > row.sellRaw
                        : row.buyRaw < row.sellRaw;
                      const tied = row.sellRaw === row.buyRaw;

                      return (
                        <tr
                          key={row.label}
                          className={cn(
                            "border-b border-[var(--border)] last:border-0",
                            idx % 2 === 0
                              ? "bg-[var(--card)]"
                              : "bg-[var(--muted)]/30",
                          )}
                        >
                          <td
                            className={cn(
                              "px-4 py-2.5 text-left",
                              !tied && betterClass(sellBetter, buyBetter),
                            )}
                          >
                            {row.sellValue}
                            {row.label === "Form" && trendIcon(sellPlayer.form_trend)}
                          </td>
                          <td className="px-4 py-2.5 text-center text-xs font-medium text-[var(--muted-foreground)]">
                            {row.label}
                          </td>
                          <td
                            className={cn(
                              "px-4 py-2.5 text-right",
                              !tied && betterClass(buyBetter, sellBetter),
                            )}
                          >
                            {row.buyValue}
                            {row.label === "Form" && trendIcon(buyPlayer.form_trend)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Score Breakdown — Population Pyramid */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Score Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between mb-2 text-xs text-[var(--muted-foreground)]">
                <span className="text-red-500 font-medium">{sellPlayer.web_name}</span>
                <span className="text-green-500 font-medium">{buyPlayer.web_name}</span>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={pyramidData}
                  layout="vertical"
                  margin={{ top: 0, right: 20, left: 20, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    domain={[-20, 20]}
                    tickFormatter={(v: number) => String(Math.abs(v))}
                    tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={70}
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(value: unknown, name: unknown) => [
                      Math.abs(Number(value)).toFixed(1),
                      String(name) === "sell" ? sellPlayer.web_name : buyPlayer.web_name,
                    ]}
                  />
                  <ReferenceLine x={0} stroke="var(--border)" />
                  <Bar dataKey="sell" name="sell" stackId="a">
                    {pyramidData.map((_, i) => (
                      <Cell key={i} fill="var(--chart-1)" opacity={0.8} />
                    ))}
                  </Bar>
                  <Bar dataKey="buy" name="buy" stackId="a">
                    {pyramidData.map((_, i) => (
                      <Cell key={i} fill="var(--chart-2)" opacity={0.8} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Form Sparklines */}
          <div className="grid gap-4 md:grid-cols-2">
            <SparklineCard
              title={sellPlayer.web_name}
              data={sellHistory}
              color="var(--chart-1)"
              borderClass="border-l-4 border-l-red-500"
            />
            <SparklineCard
              title={buyPlayer.web_name}
              data={buyHistory}
              color="var(--chart-2)"
              borderClass="border-l-4 border-l-green-500"
            />
          </div>

          {/* AI Assessments */}
          {(sellPlayer.llm_summary || buyPlayer.llm_summary) && (
            <div className="grid gap-4 md:grid-cols-2">
              {sellPlayer.llm_summary && (
                <div className="rounded-lg border border-[var(--ai-border)] bg-[var(--ai-bg)] p-4">
                  <div className="flex items-center gap-1.5 mb-2">
                    <Sparkles className="h-3.5 w-3.5 text-[var(--accent)]" />
                    <span className="text-xs font-semibold text-[var(--accent)]">
                      AI on {sellPlayer.web_name}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
                    {sellPlayer.llm_summary}
                  </p>
                </div>
              )}
              {buyPlayer.llm_summary && (
                <div className="rounded-lg border border-[var(--ai-border)] bg-[var(--ai-bg)] p-4">
                  <div className="flex items-center gap-1.5 mb-2">
                    <Sparkles className="h-3.5 w-3.5 text-[var(--accent)]" />
                    <span className="text-xs font-semibold text-[var(--accent)]">
                      AI on {buyPlayer.web_name}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
                    {buyPlayer.llm_summary}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Fixture Outlook */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Fixture Outlook
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs font-medium text-[var(--muted-foreground)] mb-2">
                    {sellPlayer.web_name} ({sellPlayer.team_short})
                  </p>
                  <div className="flex gap-1.5 flex-wrap">
                    {sellPlayer.fdr_next_3 != null && (
                      <Badge className={cn(fdrClass(sellPlayer.fdr_next_3), "text-xs")}>
                        FDR 3: {sellPlayer.fdr_next_3.toFixed(1)}
                      </Badge>
                    )}
                    {sellPlayer.fdr_next_6 != null && (
                      <Badge className={cn(fdrClass(sellPlayer.fdr_next_6), "text-xs")}>
                        FDR 6: {sellPlayer.fdr_next_6.toFixed(1)}
                      </Badge>
                    )}
                    {sellPlayer.best_gameweeks &&
                      sellPlayer.best_gameweeks.map((gw) => (
                        <span
                          key={gw}
                          className={cn(
                            "rounded px-1.5 py-0.5 text-[10px] font-medium",
                            fdrClass(2),
                          )}
                        >
                          GW{gw}
                        </span>
                      ))}
                  </div>
                  {sellPlayer.fixture_recommendation && (
                    <p className="text-xs text-[var(--muted-foreground)] mt-2">
                      {sellPlayer.fixture_recommendation}
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-xs font-medium text-[var(--muted-foreground)] mb-2">
                    {buyPlayer.web_name} ({buyPlayer.team_short})
                  </p>
                  <div className="flex gap-1.5 flex-wrap">
                    {buyPlayer.fdr_next_3 != null && (
                      <Badge className={cn(fdrClass(buyPlayer.fdr_next_3), "text-xs")}>
                        FDR 3: {buyPlayer.fdr_next_3.toFixed(1)}
                      </Badge>
                    )}
                    {buyPlayer.fdr_next_6 != null && (
                      <Badge className={cn(fdrClass(buyPlayer.fdr_next_6), "text-xs")}>
                        FDR 6: {buyPlayer.fdr_next_6.toFixed(1)}
                      </Badge>
                    )}
                    {buyPlayer.best_gameweeks &&
                      buyPlayer.best_gameweeks.map((gw) => (
                        <span
                          key={gw}
                          className={cn(
                            "rounded px-1.5 py-0.5 text-[10px] font-medium",
                            fdrClass(2),
                          )}
                        >
                          GW{gw}
                        </span>
                      ))}
                  </div>
                  {buyPlayer.fixture_recommendation && (
                    <p className="text-xs text-[var(--muted-foreground)] mt-2">
                      {buyPlayer.fixture_recommendation}
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Verdict */}
          {verdictText && (
            <Card className="border-[var(--accent)]/40 bg-[var(--accent)]/5">
              <CardContent className="pt-5">
                <div className="flex items-start gap-3">
                  <div className="rounded-full bg-[var(--accent)]/10 p-2 shrink-0">
                    <Zap className="h-5 w-5 text-[var(--accent)]" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-base mb-1">Verdict</h3>
                    <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
                      {verdictText}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Prompt when no comparison yet */}
      {!bothSelected && (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <ShieldCheck className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-lg font-medium">
            {!sellPlayer && !buyPlayer
              ? "Select a player to sell and a player to buy"
              : !sellPlayer
                ? "Now select a player to sell"
                : "Now select a player to buy"}
          </p>
          <p className="text-sm mt-1">
            Pick one from each panel above to compare
          </p>
        </div>
      )}
    </div>
  );
}

/* ---------- Sub-components ---------- */

function SparklineCard({
  title,
  data,
  color,
  borderClass,
}: {
  title: string;
  data: PlayerHistory[];
  color: string;
  borderClass: string;
}) {
  if (data.length === 0) {
    return (
      <Card className={borderClass}>
        <CardContent className="pt-4">
          <p className="text-xs font-medium mb-2">{title} — Form Trend</p>
          <p className="text-xs text-[var(--muted-foreground)]">
            No history data available
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={borderClass}>
      <CardContent className="pt-4">
        <p className="text-xs font-medium mb-2">{title} — FPL Score Trend</p>
        <ResponsiveContainer width="100%" height={80}>
          <LineChart data={data}>
            <XAxis
              dataKey="gameweek"
              tick={{ fontSize: 9, fill: "var(--muted-foreground)" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis hide domain={["dataMin - 5", "dataMax + 5"]} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value: unknown) => [Number(value).toFixed(1), "FPL Score"]}
              labelFormatter={(gw) => `GW ${gw}`}
            />
            <Line
              type="monotone"
              dataKey="fpl_score"
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

/* ---------- Verdict builder ---------- */

function buildVerdict(sell: PlayerDashboard, buy: PlayerDashboard): string {
  const scoreDiff = buy.fpl_score - sell.fpl_score;
  const fdrSell = sell.fdr_next_3 ?? 3;
  const fdrBuy = buy.fdr_next_3 ?? 3;
  const fdrDiff = fdrSell - fdrBuy; // positive means buy has easier fixtures

  const parts: string[] = [];

  if (scoreDiff > 5) {
    parts.push(
      `Strong upgrade. ${buy.web_name} scores ${scoreDiff.toFixed(1)} points higher than ${sell.web_name} on the FPL Score index.`,
    );
  } else if (scoreDiff >= -5) {
    parts.push(
      `Lateral move. The FPL Score difference is only ${Math.abs(scoreDiff).toFixed(1)} points — consider the fixture run before committing.`,
    );
  } else {
    parts.push(
      `Downgrade. ${buy.web_name} scores ${Math.abs(scoreDiff).toFixed(1)} points lower — only worthwhile if you are freeing budget for a bigger upgrade elsewhere.`,
    );
  }

  if (fdrDiff > 0.5) {
    parts.push(
      `Better fixtures ahead: ${buy.web_name} has an easier next-3 FDR (${fdrBuy.toFixed(1)} vs ${fdrSell.toFixed(1)}).`,
    );
  } else if (fdrDiff < -0.5) {
    parts.push(
      `Tougher fixtures ahead: ${buy.web_name} faces harder games in the next 3 (${fdrBuy.toFixed(1)} vs ${fdrSell.toFixed(1)}).`,
    );
  }

  const priceDelta = sell.price - buy.price;
  if (priceDelta > 0.5) {
    parts.push(`Frees up ${formatPrice(priceDelta)} in budget.`);
  }

  return parts.join(" ");
}
