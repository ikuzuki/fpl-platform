import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, Sparkles, AlertTriangle, Newspaper, Calendar } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { TransferPick, PlayerDashboard } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import {
  formatPrice,
  positionColor,
  recommendationStyle,
  scoreColor,
  fdrClass,
  cn,
} from "@/lib/utils";

type Filter = "all" | "buy" | "sell" | "watch" | "hold";
type SortKey = "fpl_score" | "price" | "form" | "fdr_next_3";

export function TransfersPage() {
  const { data, loading, error } = useApi(
    () => Promise.all([api.transfers(), api.players()]).then(([t, p]) => ({ transfers: t, players: p })),
    { transfers: [] as TransferPick[], players: [] as PlayerDashboard[] },
  );

  const [searchParams, setSearchParams] = useSearchParams();
  const filter = (searchParams.get("filter") as Filter) ?? "all";
  const sortBy = (searchParams.get("sort") as SortKey) ?? "fpl_score";
  const [expanded, setExpanded] = useState<number | null>(null);

  const setFilter = (f: Filter) => {
    const next = new URLSearchParams(searchParams);
    if (f !== "all") next.set("filter", f);
    else next.delete("filter");
    setSearchParams(next, { replace: true });
  };

  const setSortBy = (s: SortKey) => {
    const next = new URLSearchParams(searchParams);
    next.set("sort", s);
    setSearchParams(next, { replace: true });
  };

  const filtered = useMemo(() => {
    let result = filter === "all" ? data.transfers : data.transfers.filter((p) => p.recommendation === filter);
    result = [...result].sort((a, b) => {
      if (sortBy === "fdr_next_3") return (a.fdr_next_3 ?? 3) - (b.fdr_next_3 ?? 3);
      return (b[sortBy] ?? 0) - (a[sortBy] ?? 0);
    });
    return result;
  }, [data.transfers, filter, sortBy]);

  const counts = {
    all: data.transfers.length,
    buy: data.transfers.filter((p) => p.recommendation === "buy").length,
    sell: data.transfers.filter((p) => p.recommendation === "sell").length,
    watch: data.transfers.filter((p) => p.recommendation === "watch").length,
    hold: data.transfers.filter((p) => p.recommendation === "hold").length,
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

  if (error) return <ErrorCard message={error} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">Transfer Hub</h1>
        <div className="flex items-center gap-2" role="group" aria-label="Sort by">
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
              aria-pressed={sortBy === key}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2 flex-wrap" role="group" aria-label="Filter recommendations">
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
              aria-pressed={filter === f}
            >
              {f === "all" ? "All" : style?.label} ({counts[f]})
            </button>
          );
        })}
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {filtered.slice(0, 30).map((player) => {
          const detail = data.players.find((p) => p.player_id === player.player_id);
          return (
            <TransferCard
              key={player.player_id}
              player={player}
              detail={detail}
              isExpanded={expanded === player.player_id}
              onToggle={() =>
                setExpanded(expanded === player.player_id ? null : player.player_id)
              }
            />
          );
        })}
      </div>

      {filtered.length > 30 && (
        <p className="text-center text-sm text-[var(--muted-foreground)]">
          Showing top 30 of {filtered.length} players
        </p>
      )}

      {filtered.length === 0 && (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <p>No players in this category</p>
          <button onClick={() => setFilter("all")} className="mt-2 text-sm text-[var(--accent)] hover:underline">
            Show all
          </button>
        </div>
      )}
    </div>
  );
}

function TransferCard({
  player,
  detail,
  isExpanded,
  onToggle,
}: {
  player: TransferPick;
  detail?: PlayerDashboard;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const rec = recommendationStyle(player.recommendation);

  return (
    <Card
      className={cn("hover:shadow-md transition-shadow border-l-4 cursor-pointer", rec.border)}
      onClick={onToggle}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{player.web_name}</CardTitle>
            <p className="text-xs text-[var(--muted-foreground)]">{player.team_name}</p>
          </div>
          <div className="flex gap-1.5 items-center">
            <Badge className={positionColor(player.position)}>{player.position}</Badge>
            <Badge className={cn(rec.bg, rec.text, "font-semibold")}>{rec.label}</Badge>
            <ChevronDown
              className={cn(
                "h-4 w-4 text-[var(--muted-foreground)] transition-transform duration-200",
                isExpanded && "rotate-180",
              )}
            />
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
        <ul className="space-y-1.5">
          {player.recommendation_reasons.slice(0, 3).map((reason, i) => (
            <li key={i} className="text-sm text-[var(--muted-foreground)] flex gap-2 items-start">
              <span
                className={cn(
                  "mt-0.5 font-bold text-base leading-none",
                  player.recommendation === "sell" ? "text-red-400" : "text-green-400",
                )}
              >
                {player.recommendation === "sell" ? "\u2212" : "+"}
              </span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>

        {isExpanded && detail && (
          <div className="expand-enter">
            <div>
              <div
                className="mt-4 pt-4 border-t border-[var(--border)] space-y-3"
                onClick={(e) => e.stopPropagation()}
              >
                {detail.llm_summary && (
                  <div className="rounded-lg border border-[var(--ai-border)] bg-[var(--ai-bg)] p-3">
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-[var(--accent)]" />
                      <span className="text-xs font-semibold text-[var(--accent)]">AI Assessment</span>
                    </div>
                    <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">{detail.llm_summary}</p>
                  </div>
                )}

                {detail.injury_risk != null && (
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-3.5 w-3.5 text-[var(--muted-foreground)] mt-0.5 shrink-0" />
                    <div>
                      <span className="text-xs font-semibold">Injury: {detail.injury_risk}/10</span>
                      {detail.injury_reasoning && (
                        <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{detail.injury_reasoning}</p>
                      )}
                    </div>
                  </div>
                )}

                {detail.sentiment_label && (
                  <div className="flex items-start gap-2">
                    <Newspaper className="h-3.5 w-3.5 text-[var(--muted-foreground)] mt-0.5 shrink-0" />
                    <div>
                      <span className="text-xs font-semibold capitalize">Sentiment: {detail.sentiment_label}</span>
                      {detail.key_themes && detail.key_themes.length > 0 && (
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {detail.key_themes.map((t) => (
                            <Badge key={t} className="bg-[var(--muted)] text-[var(--muted-foreground)] text-[10px]">{t}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {detail.fixture_recommendation && (
                  <div className="flex items-start gap-2">
                    <Calendar className="h-3.5 w-3.5 text-[var(--muted-foreground)] mt-0.5 shrink-0" />
                    <div>
                      <span className="text-xs font-semibold">Fixture Outlook</span>
                      <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{detail.fixture_recommendation}</p>
                      {detail.best_gameweeks && detail.best_gameweeks.length > 0 && (
                        <div className="flex gap-1 mt-1">
                          {detail.best_gameweeks.map((gw) => (
                            <span key={gw} className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", fdrClass(2))}>
                              GW{gw}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <div className="text-[var(--muted-foreground)] uppercase tracking-wider text-[10px]">{label}</div>
      <div className={cn("font-semibold text-sm", className)}>{value}</div>
    </div>
  );
}
