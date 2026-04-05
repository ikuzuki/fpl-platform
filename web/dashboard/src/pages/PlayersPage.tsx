import { useEffect, useMemo, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";
import type { PlayerDashboard } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  formatPrice,
  positionColor,
  scoreColor,
  cn,
} from "@/lib/utils";

const col = createColumnHelper<PlayerDashboard>();

const columns = [
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
    cell: (info) => (
      <span className={cn("font-bold text-sm", scoreColor(info.getValue()))}>
        {info.getValue().toFixed(1)}
      </span>
    ),
    size: 90,
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
      if (!v) return <span className="text-[var(--muted-foreground)]">-</span>;
      const style =
        v === "improving"
          ? "text-green-600"
          : v === "declining"
            ? "text-red-500"
            : "text-gray-500";
      return <span className={cn("text-xs capitalize", style)}>{v}</span>;
    },
    size: 80,
  }),
  col.accessor("points_per_million", {
    header: "Pts/M",
    cell: (info) => info.getValue().toFixed(1),
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
      if (v == null) return <span className="text-[var(--muted-foreground)]">-</span>;
      const color =
        v >= 7 ? "bg-red-100 text-red-800" : v >= 4 ? "bg-amber-100 text-amber-800" : "bg-green-100 text-green-800";
      return <Badge className={color}>{v}/10</Badge>;
    },
    size: 65,
  }),
  col.accessor("fdr_next_3", {
    header: "FDR",
    cell: (info) => {
      const v = info.getValue();
      if (v == null) return "-";
      return v.toFixed(1);
    },
    size: 50,
  }),
];

const positions = ["All", "GKP", "DEF", "MID", "FWD"];

export function PlayersPage() {
  const [data, setData] = useState<PlayerDashboard[]>([]);
  const [loading, setLoading] = useState(true);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "fpl_score", desc: true },
  ]);
  const [posFilter, setPosFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    api.players().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  const filtered = useMemo(() => {
    let result = data;
    if (posFilter !== "All") result = result.filter((p) => p.position === posFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.web_name.toLowerCase().includes(q) ||
          p.team_name.toLowerCase().includes(q),
      );
    }
    return result;
  }, [data, posFilter, search]);

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--muted-foreground)]">Loading players...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Player Rankings</h1>
        <span className="text-sm text-[var(--muted-foreground)]">
          GW{data[0]?.gameweek} &middot; {filtered.length} players
        </span>
      </div>

      <div className="flex gap-3 items-center">
        <input
          type="text"
          placeholder="Search player or team..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)] w-64"
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
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === "asc" ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : header.column.getIsSorted() === "desc" ? (
                          <ChevronDown className="h-3 w-3" />
                        ) : (
                          <ArrowUpDown className="h-3 w-3 opacity-30" />
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <>
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
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                  {expanded === row.original.player_id && (
                    <tr key={`${row.id}-detail`} className="bg-[var(--muted)]/30">
                      <td colSpan={columns.length} className="px-6 py-4">
                        <PlayerDetail player={row.original} />
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function PlayerDetail({ player }: { player: PlayerDashboard }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
      <div>
        <h4 className="font-semibold mb-2">AI Summary</h4>
        <p className="text-[var(--muted-foreground)] leading-relaxed">
          {player.llm_summary ?? "No summary available"}
        </p>
        {player.key_themes && player.key_themes.length > 0 && (
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {player.key_themes.map((t) => (
              <Badge key={t} className="bg-[var(--muted)] text-[var(--muted-foreground)]">
                {t}
              </Badge>
            ))}
          </div>
        )}
      </div>
      <div>
        <h4 className="font-semibold mb-2">Stats</h4>
        <dl className="space-y-1 text-[var(--muted-foreground)]">
          <StatRow label="Goals" value={player.goals_scored} />
          <StatRow label="Assists" value={player.assists} />
          <StatRow label="Clean sheets" value={player.clean_sheets} />
          <StatRow label="xG" value={player.xg?.toFixed(1) ?? "n/a"} />
          <StatRow label="xA" value={player.xa?.toFixed(1) ?? "n/a"} />
          <StatRow
            label="xG delta"
            value={player.xg_delta != null ? `${player.xg_delta > 0 ? "+" : ""}${player.xg_delta.toFixed(1)}` : "n/a"}
          />
          <StatRow label="ICT Index" value={player.ict_index.toFixed(0)} />
        </dl>
      </div>
      <div>
        <h4 className="font-semibold mb-2">Fixture Outlook</h4>
        <p className="text-[var(--muted-foreground)] leading-relaxed">
          {player.fixture_recommendation ?? "No fixture data"}
        </p>
        {player.best_gameweeks && player.best_gameweeks.length > 0 && (
          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
            Best GWs: {player.best_gameweeks.join(", ")}
          </p>
        )}
        {player.injury_reasoning && (
          <div className="mt-3">
            <h4 className="font-semibold mb-1">Injury</h4>
            <p className="text-[var(--muted-foreground)]">{player.injury_reasoning}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between">
      <dt>{label}</dt>
      <dd className="font-medium text-[var(--foreground)]">{value}</dd>
    </div>
  );
}
