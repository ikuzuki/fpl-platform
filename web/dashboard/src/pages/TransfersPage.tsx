import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TransferPick } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  formatPrice,
  positionColor,
  recommendationStyle,
  scoreColor,
  cn,
} from "@/lib/utils";

type Filter = "all" | "buy" | "sell" | "watch" | "hold";

export function TransfersPage() {
  const [data, setData] = useState<TransferPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    api.transfers().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  const filtered = filter === "all" ? data : data.filter((p) => p.recommendation === filter);
  const counts = {
    all: data.length,
    buy: data.filter((p) => p.recommendation === "buy").length,
    sell: data.filter((p) => p.recommendation === "sell").length,
    watch: data.filter((p) => p.recommendation === "watch").length,
    hold: data.filter((p) => p.recommendation === "hold").length,
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--muted-foreground)]">Loading transfers...</div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Transfer Hub</h1>

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
        {filtered
          .sort((a, b) => {
            if (a.recommendation === "buy" && b.recommendation !== "buy") return -1;
            if (a.recommendation !== "buy" && b.recommendation === "buy") return 1;
            if (a.recommendation === "sell" && b.recommendation !== "sell") return -1;
            if (a.recommendation !== "sell" && b.recommendation === "sell") return 1;
            return b.fpl_score - a.fpl_score;
          })
          .slice(0, 30)
          .map((player) => (
            <TransferCard key={player.player_id} player={player} />
          ))}
      </div>

      {filtered.length > 30 && (
        <p className="text-center text-sm text-[var(--muted-foreground)]">
          Showing top 30 of {filtered.length} players
        </p>
      )}
    </div>
  );
}

function TransferCard({ player }: { player: TransferPick }) {
  const rec = recommendationStyle(player.recommendation);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{player.web_name}</CardTitle>
            <p className="text-xs text-[var(--muted-foreground)]">
              {player.team_name}
            </p>
          </div>
          <div className="flex gap-1.5 items-center">
            <Badge className={positionColor(player.position)}>{player.position}</Badge>
            <Badge className={cn(rec.bg, rec.text)}>{rec.label}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-4 gap-2 text-center text-xs mb-3">
          <Stat label="Score" value={player.fpl_score.toFixed(1)} className={scoreColor(player.fpl_score)} />
          <Stat label="Price" value={formatPrice(player.price)} />
          <Stat label="Form" value={player.form.toFixed(1)} />
          <Stat label="FDR" value={player.fdr_next_3?.toFixed(1) ?? "-"} />
        </div>
        <ul className="space-y-1">
          {player.recommendation_reasons.slice(0, 3).map((reason, i) => (
            <li key={i} className="text-xs text-[var(--muted-foreground)] flex gap-1.5">
              <span className={cn("mt-0.5", player.recommendation === "sell" ? "text-red-400" : "text-green-400")}>
                {player.recommendation === "sell" ? "\u2212" : "+"}
              </span>
              {reason}
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
