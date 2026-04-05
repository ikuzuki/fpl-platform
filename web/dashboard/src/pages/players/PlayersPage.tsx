import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { PlayerDashboard, TransferPick, PlayerHistory } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import {
  formatPrice,
  positionColor,
  scoreColor,
  scoreBarColor,
  heatmapBg,
  playerTier,
  cn,
} from "@/lib/utils";
import { PlayerDetail } from "./PlayerDetail";
import { XgScatter } from "./XgScatter";
import { OwnershipBubble } from "./OwnershipBubble";
import { MomentumHeatmap } from "./MomentumHeatmap";

const col = createColumnHelper<PlayerDashboard>();

const positions = ["All", "GKP", "DEF", "MID", "FWD"];

export function PlayersPage() {
  const { data, loading, error } = useApi(
    () => Promise.all([api.players(), api.transfers(), api.history()]).then(([p, t, h]) => ({ players: p, transfers: t, history: h })),
    { players: [] as PlayerDashboard[], transfers: [] as TransferPick[], history: [] as PlayerHistory[] },
  );

  const [searchParams, setSearchParams] = useSearchParams();
  const posFilter = searchParams.get("pos") ?? "All";
  const search = searchParams.get("q") ?? "";

  const [sorting, setSorting] = useState<SortingState>([
    { id: "fpl_score", desc: true },
  ]);
  const [expanded, setExpanded] = useState<number | null>(null);

  const setSearch = (q: string) => {
    const next = new URLSearchParams(searchParams);
    if (q) next.set("q", q);
    else next.delete("q");
    setSearchParams(next, { replace: true });
  };

  const setPosFilter = (pos: string) => {
    const next = new URLSearchParams(searchParams);
    if (pos !== "All") next.set("pos", pos);
    else next.delete("pos");
    setSearchParams(next, { replace: true });
  };

  const filtered = useMemo(() => {
    let result = data.players;
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
  }, [data.players, posFilter, search]);

  const ppmRange = useMemo(() => {
    const vals = filtered.map((p) => p.points_per_million);
    return { min: Math.min(...vals), max: Math.max(...vals) };
  }, [filtered]);

  const columns = useMemo(
    () => [
      col.display({
        id: "expand",
        cell: ({ row }) => (
          <button
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-transform duration-200"
            aria-label={expanded === row.original.player_id ? "Collapse details" : "Expand details"}
          >
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
                role="progressbar"
                aria-valuenow={v}
                aria-valuemin={0}
                aria-valuemax={100}
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
          <span className={heatmapBg(info.getValue(), ppmRange.min, ppmRange.max)}>
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
  if (error) return <ErrorCard message={error} />;

  const topPick = data.transfers.find((t) => t.recommendation === "buy");

  return (
    <div className="space-y-6">
      {/* Hero Summary Strip */}
      <div className="grid gap-4 md:grid-cols-4">
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
                    {topPick.team_name} &middot; {formatPrice(topPick.price)}
                  </p>
                </div>
                <div className="text-right">
                  <p className={cn("text-2xl font-bold", scoreColor(topPick.fpl_score))}>
                    {topPick.fpl_score.toFixed(1)}
                  </p>
                  <p className="text-xs text-[var(--muted-foreground)]">FPL Score</p>
                </div>
              </div>
              <ul className="mt-2 space-y-0.5">
                {topPick.recommendation_reasons.slice(0, 2).map((r, i) => (
                  <li key={i} className="text-xs text-[var(--muted-foreground)] flex gap-1.5">
                    <span className="text-green-500">+</span> {r}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider mb-1">
              Gameweek
            </p>
            <p className="text-3xl font-bold">{data.players[0]?.gameweek}</p>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              {data.players.length} players tracked
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
              {data.players.filter((p) => p.injury_risk != null && p.injury_risk >= 5).length}
            </p>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              players at risk (5+/10)
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Table Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Player Rankings</h1>
        <div className="flex gap-3 items-center flex-wrap">
          <div>
            <label htmlFor="player-search" className="sr-only">Search players</label>
            <input
              id="player-search"
              type="text"
              placeholder="Search player or team..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)] w-56"
            />
          </div>
          <div className="flex gap-1" role="group" aria-label="Filter by position">
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
                aria-pressed={posFilter === pos}
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
          <table className="w-full text-sm" aria-label="Player rankings">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-[var(--border)]">
                  {hg.headers.map((header) => {
                    const sorted = header.column.getIsSorted();
                    return (
                      <th
                        key={header.id}
                        className="px-3 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider cursor-pointer select-none hover:text-[var(--foreground)]"
                        style={{ width: header.getSize() }}
                        onClick={header.column.getToggleSortingHandler()}
                        aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"}
                      >
                        <div className="flex items-center gap-1">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {header.column.getCanSort() &&
                            (sorted === "asc" ? (
                              <ChevronUp className="h-3 w-3" />
                            ) : sorted === "desc" ? (
                              <ChevronDown className="h-3 w-3" />
                            ) : (
                              <ArrowUpDown className="h-3 w-3 opacity-30" />
                            ))}
                        </div>
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row, idx) => {
                const rank = row.original.fpl_score_rank;
                const prevRank =
                  idx > 0
                    ? table.getRowModel().rows[idx - 1]?.original.fpl_score_rank
                    : null;
                const tier = playerTier(rank);
                const prevTier = prevRank != null ? playerTier(prevRank) : null;
                const showTierHeader = tier !== prevTier && tier !== null;
                const isExpanded = expanded === row.original.player_id;

                return (
                  <>
                    {showTierHeader && (
                      <tr key={`tier-${tier}`} className="bg-[var(--muted)]/50">
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
                      className={cn(
                        "border-b border-[var(--border)] hover:bg-[var(--muted)]/50 cursor-pointer transition-colors",
                      )}
                      onClick={() =>
                        setExpanded(isExpanded ? null : row.original.player_id)
                      }
                      role="button"
                      tabIndex={0}
                      aria-expanded={isExpanded}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setExpanded(isExpanded ? null : row.original.player_id);
                        }
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-3 py-2.5">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                    {isExpanded && (
                      <tr key={`${row.id}-detail`} className="bg-[var(--muted)]/20">
                        <td colSpan={columns.length}>
                          <div className="expand-enter">
                            <div>
                              <div className="px-6 py-5">
                                <PlayerDetail player={row.original} />
                              </div>
                            </div>
                          </div>
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

      <XgScatter players={filtered} />
      <OwnershipBubble players={filtered} />

      {data.history.length > 0 && <MomentumHeatmap history={data.history} />}

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
