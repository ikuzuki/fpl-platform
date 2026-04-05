import { useEffect, useMemo, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import {
  ArrowUpDown,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  Shield,
} from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { PlayerDashboard, TransferPick } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  formatPrice,
  formatNumber,
  positionColor,
  scoreColor,
  scoreBarColor,
  heatmapBg,
  playerTier,
  fdrClass,
  cn,
} from "@/lib/utils";

const col = createColumnHelper<PlayerDashboard>();

const positions = ["All", "GKP", "DEF", "MID", "FWD"];

export function PlayersPage() {
  const [data, setData] = useState<PlayerDashboard[]>([]);
  const [transfers, setTransfers] = useState<TransferPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "fpl_score", desc: true },
  ]);
  const [posFilter, setPosFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.players(), api.transfers()]).then(([p, t]) => {
      setData(p);
      setTransfers(t);
      setLoading(false);
    });
  }, []);

  const filtered = useMemo(() => {
    let result = data;
    if (posFilter !== "All")
      result = result.filter((p) => p.position === posFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.web_name.toLowerCase().includes(q) ||
          p.team_name.toLowerCase().includes(q) ||
          p.team_short.toLowerCase().includes(q),
      );
    }
    return result;
  }, [data, posFilter, search]);

  const ppmRange = useMemo(() => {
    const vals = filtered.map((p) => p.points_per_million);
    return { min: Math.min(...vals), max: Math.max(...vals) };
  }, [filtered]);

  const columns = useMemo(
    () => [
      col.display({
        id: "expand",
        cell: ({ row }) => (
          <button className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-transform duration-200">
            {expanded === row.original.player_id ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        ),
        size: 32,
      }),
      col.accessor("fpl_score_rank", {
        header: "#",
        cell: (info) => (
          <span className="text-[var(--muted-foreground)] text-xs font-mono">
            {info.getValue()}
          </span>
        ),
        size: 40,
      }),
      col.accessor("web_name", {
        header: "Player",
        cell: (info) => (
          <div>
            <div className="font-medium">{info.getValue()}</div>
            <div className="text-xs text-[var(--muted-foreground)]">
              {info.row.original.team_short}
            </div>
          </div>
        ),
        size: 140,
      }),
      col.accessor("position", {
        header: "Pos",
        cell: (info) => (
          <Badge className={positionColor(info.getValue())}>
            {info.getValue()}
          </Badge>
        ),
        size: 60,
      }),
      col.accessor("fpl_score", {
        header: "FPL Score",
        cell: (info) => {
          const v = info.getValue();
          return (
            <div>
              <span className={cn("font-bold text-sm", scoreColor(v))}>
                {v.toFixed(1)}
              </span>
              <div
                className={cn("score-bar", scoreBarColor(v))}
                style={{ width: `${v}%` }}
              />
            </div>
          );
        },
        size: 100,
      }),
      col.accessor("price", {
        header: "Price",
        cell: (info) => formatPrice(info.getValue()),
        size: 70,
      }),
      col.accessor("total_points", { header: "Pts", size: 50 }),
      col.accessor("form", {
        header: "Form",
        cell: (info) => info.getValue().toFixed(1),
        size: 55,
      }),
      col.accessor("form_trend", {
        header: "Trend",
        cell: (info) => {
          const v = info.getValue();
          if (!v)
            return <span className="text-[var(--muted-foreground)]">-</span>;
          if (v === "improving")
            return (
              <span className="flex items-center gap-1 text-green-600 dark:text-green-400 text-xs">
                <TrendingUp className="h-3 w-3" /> Up
              </span>
            );
          if (v === "declining")
            return (
              <span className="flex items-center gap-1 text-red-500 dark:text-red-400 text-xs">
                <TrendingDown className="h-3 w-3" /> Down
              </span>
            );
          return (
            <span className="flex items-center gap-1 text-[var(--muted-foreground)] text-xs">
              <Minus className="h-3 w-3" /> Flat
            </span>
          );
        },
        size: 70,
      }),
      col.accessor("points_per_million", {
        header: "Pts/M",
        cell: (info) => (
          <span
            className={heatmapBg(info.getValue(), ppmRange.min, ppmRange.max)}
          >
            {info.getValue().toFixed(1)}
          </span>
        ),
        size: 60,
      }),
      col.accessor("ownership_pct", {
        header: "Own%",
        cell: (info) => `${info.getValue().toFixed(1)}%`,
        size: 60,
      }),
      col.accessor("injury_risk", {
        header: "Injury",
        cell: (info) => {
          const v = info.getValue();
          if (v == null)
            return <span className="text-[var(--muted-foreground)]">-</span>;
          const color =
            v >= 7
              ? "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
              : v >= 4
                ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                : "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300";
          return <Badge className={color}>{v}/10</Badge>;
        },
        size: 65,
      }),
      col.accessor("fdr_next_3", {
        header: "FDR",
        cell: (info) => {
          const v = info.getValue();
          if (v == null) return "-";
          return <span className={cn("text-xs")}>{v.toFixed(1)}</span>;
        },
        size: 50,
      }),
    ],
    [expanded, ppmRange],
  );

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (loading) return <TableSkeleton rows={12} />;

  const topPick = transfers.find((t) => t.recommendation === "buy");
  return (
    <div className="space-y-6">
      {/* Hero Summary Strip */}
      <div className="grid gap-4 md:grid-cols-4">
        {/* AI Pick of the Week */}
        {topPick && (
          <Card className="md:col-span-2 border-l-4 border-l-[var(--accent)] bg-[var(--ai-bg)] border-[var(--ai-border)]">
            <CardContent className="pt-4">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-4 w-4 text-[var(--accent)]" />
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">
                  AI Pick of the Week
                </span>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xl font-bold">{topPick.web_name}</p>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {topPick.team_name} &middot;{" "}
                    {formatPrice(topPick.price)}
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={cn(
                      "text-2xl font-bold",
                      scoreColor(topPick.fpl_score),
                    )}
                  >
                    {topPick.fpl_score.toFixed(1)}
                  </p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    FPL Score
                  </p>
                </div>
              </div>
              <ul className="mt-2 space-y-0.5">
                {topPick.recommendation_reasons.slice(0, 2).map((r, i) => (
                  <li
                    key={i}
                    className="text-xs text-[var(--muted-foreground)] flex gap-1.5"
                  >
                    <span className="text-green-500">+</span> {r}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* KPI Cards */}
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider mb-1">
              Gameweek
            </p>
            <p className="text-3xl font-bold">{data[0]?.gameweek}</p>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              {data.length} players tracked
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider mb-1">
              <Shield className="inline h-3 w-3 mr-1" />
              Injury Alerts
            </p>
            <p className="text-3xl font-bold text-red-500">
              {data.filter((p) => p.injury_risk != null && p.injury_risk >= 5)
                .length}
            </p>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              players at risk (5+/10)
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Table Controls */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Player Rankings</h1>
        <div className="flex gap-3 items-center">
          <input
            type="text"
            placeholder="Search player or team..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)] w-56"
          />
          <div className="flex gap-1">
            {positions.map((pos) => (
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
        </div>
      </div>

      {/* Player Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-[var(--border)]">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-3 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider cursor-pointer select-none hover:text-[var(--foreground)]"
                      style={{ width: header.getSize() }}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {header.column.getCanSort() &&
                          (header.column.getIsSorted() === "asc" ? (
                            <ChevronUp className="h-3 w-3" />
                          ) : header.column.getIsSorted() === "desc" ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ArrowUpDown className="h-3 w-3 opacity-30" />
                          ))}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row, idx) => {
                const rank = row.original.fpl_score_rank;
                const prevRank =
                  idx > 0
                    ? table.getRowModel().rows[idx - 1]?.original
                        .fpl_score_rank
                    : null;
                const tier = playerTier(rank);
                const prevTier = prevRank != null ? playerTier(prevRank) : null;
                const showTierHeader = tier !== prevTier && tier !== null;

                return (
                  <>
                    {showTierHeader && (
                      <tr
                        key={`tier-${tier}`}
                        className="bg-[var(--muted)]/50"
                      >
                        <td
                          colSpan={columns.length}
                          className="px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-[var(--accent)]"
                        >
                          {tier}
                        </td>
                      </tr>
                    )}
                    <tr
                      key={row.id}
                      className="border-b border-[var(--border)] hover:bg-[var(--muted)]/50 cursor-pointer transition-colors"
                      onClick={() =>
                        setExpanded(
                          expanded === row.original.player_id
                            ? null
                            : row.original.player_id,
                        )
                      }
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-3 py-2.5">
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )}
                        </td>
                      ))}
                    </tr>
                    {expanded === row.original.player_id && (
                      <tr
                        key={`${row.id}-detail`}
                        className="bg-[var(--muted)]/20"
                      >
                        <td colSpan={columns.length} className="px-6 py-5">
                          <PlayerDetail player={row.original} />
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <p className="text-lg">No players match your search</p>
          <button
            onClick={() => {
              setSearch("");
              setPosFilter("All");
            }}
            className="mt-2 text-sm text-[var(--accent)] hover:underline"
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}

function PlayerDetail({ player }: { player: PlayerDashboard }) {
  const radarData = [
    {
      stat: "Goals",
      value: player.goals_scored,
      max: Math.max(player.goals_scored, 20),
    },
    {
      stat: "Assists",
      value: player.assists,
      max: Math.max(player.assists, 15),
    },
    {
      stat: "xG",
      value: player.xg ?? player.goals_scored * 0.8,
      max: 20,
    },
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
                <Badge
                  key={t}
                  className="bg-[var(--muted)] text-[var(--muted-foreground)]"
                >
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

      {/* Radar Chart */}
      <div className="md:col-span-4">
        <h4 className="font-semibold text-sm mb-2">Player Profile</h4>
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

        {/* Mini Fixture Strip */}
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
                    className={cn(
                      "rounded px-2 py-0.5 text-xs font-medium",
                      fdrClass(2),
                    )}
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

function StatRow({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex justify-between">
      <dt>{label}</dt>
      <dd className="font-medium text-[var(--foreground)]">{value}</dd>
    </div>
  );
}
