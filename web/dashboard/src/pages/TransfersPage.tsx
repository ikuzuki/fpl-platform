import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { TransferPick } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import {
  formatPrice,
  positionColor,
  recommendationStyle,
  scoreColor,
  cn,
} from "@/lib/utils";

type Filter = "all" | "buy" | "sell" | "watch" | "hold";
type SortKey = "fpl_score" | "price" | "form" | "fdr_next_3";

export function TransfersPage() {
  const [data, setData] = useState<TransferPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [sortBy, setSortBy] = useState<SortKey>("fpl_score");

  useEffect(() => {
    api.transfers().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  const filtered = useMemo(() => {
    let result = filter === "all" ? data : data.filter((p) => p.recommendation === filter);
    result = [...result].sort((a, b) => {
      if (sortBy === "fdr_next_3") {
        return (a.fdr_next_3 ?? 3) - (b.fdr_next_3 ?? 3);
      }
      return (b[sortBy] ?? 0) - (a[sortBy] ?? 0);
    });
    return result;
  }, [data, filter, sortBy]);

  const counts = {
    all: data.length,
    buy: data.filter((p) => p.recommendation === "buy").length,
    sell: data.filter((p) => p.recommendation === "sell").length,
    watch: data.filter((p) => p.recommendation === "watch").length,
    hold: data.filter((p) => p.recommendation === "hold").length,
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Transfer Hub</h1>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">Transfer Hub</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--muted-foreground)]">Sort:</span>
          {(
            [
              ["fpl_score", "Score"],
              ["price", "Price"],
              ["form", "Form"],
              ["fdr_next_3", "Fixtures"],
            ] as [SortKey, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSortBy(key)}
              className={cn(
                "rounded-md px-2 py-1 text-xs font-medium transition-colors",
                sortBy === key
                  ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                  : "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--border)]",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        {(["all", "buy", "sell", "watch", "hold"] as Filter[]).map((f) => {
          const style = f === "all" ? null : recommendationStyle(f);
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                filter === f
                  ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                  : "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--border)]",
              )}
            >
              {f === "all" ? "All" : style?.label} ({counts[f]})
            </button>
          );
        })}
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {filtered.slice(0, 30).map((player) => (
          <TransferCard key={player.player_id} player={player} />
        ))}
      </div>

      {filtered.length > 30 && (
        <p className="text-center text-sm text-[var(--muted-foreground)]">
          Showing top 30 of {filtered.length} players
        </p>
      )}

      {filtered.length === 0 && (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <p>No players in this category</p>
          <button
            onClick={() => setFilter("all")}
            className="mt-2 text-sm text-[var(--accent)] hover:underline"
          >
            Show all
          </button>
        </div>
      )}
    </div>
  );
}

function TransferCard({ player }: { player: TransferPick }) {
  const rec = recommendationStyle(player.recommendation);

  return (
    <Card
      className={cn(
        "hover:shadow-md transition-shadow border-l-4",
        rec.border,
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{player.web_name}</CardTitle>
            <p className="text-xs text-[var(--muted-foreground)]">
              {player.team_name}
            </p>
          </div>
          <div className="flex gap-1.5 items-center">
            <Badge className={positionColor(player.position)}>
              {player.position}
            </Badge>
            <Badge className={cn(rec.bg, rec.text, "font-semibold")}>
              {rec.label}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-4 gap-2 text-center text-xs mb-3">
          <Stat
            label="Score"
            value={player.fpl_score.toFixed(1)}
            className={scoreColor(player.fpl_score)}
          />
          <Stat label="Price" value={formatPrice(player.price)} />
          <Stat label="Form" value={player.form.toFixed(1)} />
          <Stat label="FDR" value={player.fdr_next_3?.toFixed(1) ?? "-"} />
        </div>
        <ul className="space-y-1.5">
          {player.recommendation_reasons.slice(0, 3).map((reason, i) => (
            <li
              key={i}
              className="text-sm text-[var(--muted-foreground)] flex gap-2 items-start"
            >
              <span
                className={cn(
                  "mt-0.5 font-bold text-base leading-none",
                  player.recommendation === "sell"
                    ? "text-red-400"
                    : "text-green-400",
                )}
              >
                {player.recommendation === "sell" ? "\u2212" : "+"}
              </span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div>
      <div className="text-[var(--muted-foreground)] uppercase tracking-wider text-[10px]">
        {label}
      </div>
      <div className={cn("font-semibold text-sm", className)}>{value}</div>
    </div>
  );
}
