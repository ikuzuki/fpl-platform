import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";
import type { GameweekBriefing } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import {
  cn,
  formatPrice,
  positionColor,
  scoreColor,
  fdrClass,
} from "@/lib/utils";

export function BriefingPage() {
  const [data, setData] = useState<GameweekBriefing | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .briefing()
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-64 skeleton rounded" />
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12 text-[var(--muted-foreground)]">
        <p className="text-lg">No briefing data available</p>
        <p className="text-sm mt-1">
          Run the pipeline to generate a gameweek briefing
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">
            GW{data.gameweek} Briefing
          </h1>
          <p className="text-[var(--muted-foreground)] text-sm mt-1">
            {data.summary_stats.total_players} players analysed &middot;{" "}
            {data.summary_stats.buy_count} buys &middot;{" "}
            {data.summary_stats.sell_count} sells &middot;{" "}
            {data.summary_stats.injury_count} injury alerts
          </p>
        </div>
        <Badge className="bg-[var(--ai-bg)] text-[var(--accent)] border border-[var(--ai-border)]">
          <Sparkles className="h-3 w-3 mr-1" />
          AI-Powered
        </Badge>
      </div>

      {/* Top Picks */}
      <section>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-green-500" />
          Top Picks This Week
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {data.top_picks.map((pick, i) => (
            <Card
              key={pick.player_id}
              className={cn(
                "border-l-4 border-l-green-500",
                i === 0 &&
                  "bg-[var(--ai-bg)] border-[var(--ai-border)] md:col-span-1",
              )}
            >
              <CardContent className="pt-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="font-bold text-lg">{pick.web_name}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      {pick.team_short} &middot; {formatPrice(pick.price)}
                    </p>
                  </div>
                  <div className="text-right">
                    <Badge className={positionColor(pick.position)}>
                      {pick.position}
                    </Badge>
                    <p
                      className={cn(
                        "text-xl font-bold mt-1",
                        scoreColor(pick.fpl_score),
                      )}
                    >
                      {pick.fpl_score.toFixed(1)}
                    </p>
                  </div>
                </div>
                {pick.llm_summary && (
                  <p className="text-sm text-[var(--muted-foreground)] leading-relaxed mb-2 line-clamp-3">
                    {pick.llm_summary}
                  </p>
                )}
                <ul className="space-y-0.5">
                  {pick.reasons.map((r, j) => (
                    <li
                      key={j}
                      className="text-xs text-[var(--muted-foreground)] flex gap-1.5"
                    >
                      <span className="text-green-500">+</span> {r}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Injury Alerts */}
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            Injury Alerts
          </h2>
          <Card>
            <CardContent className="pt-4">
              {data.injury_alerts.length === 0 ? (
                <p className="text-sm text-[var(--muted-foreground)]">
                  No significant injury concerns this week
                </p>
              ) : (
                <div className="space-y-3">
                  {data.injury_alerts.map((alert) => (
                    <div
                      key={alert.player_id}
                      className="flex items-start justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">
                            {alert.web_name}
                          </span>
                          <Badge
                            className={cn(
                              positionColor(alert.position),
                              "text-[10px]",
                            )}
                          >
                            {alert.position}
                          </Badge>
                          <span className="text-xs text-[var(--muted-foreground)]">
                            {alert.team_short}
                          </span>
                        </div>
                        {alert.injury_reasoning && (
                          <p className="text-xs text-[var(--muted-foreground)] mt-0.5 line-clamp-2">
                            {alert.injury_reasoning}
                          </p>
                        )}
                      </div>
                      <Badge className="bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 shrink-0">
                        {alert.injury_risk}/10
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Fixture Spotlight */}
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Calendar className="h-5 w-5 text-[var(--accent)]" />
            Fixture Spotlight
          </h2>
          <Card>
            <CardContent className="pt-4">
              <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider mb-2">
                Best fixture runs
              </p>
              <div className="space-y-2">
                {data.best_fixtures.map((team) => (
                  <div
                    key={team.team_id}
                    className="flex items-center justify-between"
                  >
                    <span className="font-medium text-sm">
                      {team.team_name}
                    </span>
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "text-xs px-2 py-0.5 rounded font-medium",
                          fdrClass(Math.round(team.fdr_next_6)),
                        )}
                      >
                        {team.fdr_next_6} avg
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider mt-4 mb-2">
                Toughest fixture runs
              </p>
              <div className="space-y-2">
                {data.worst_fixtures.map((team) => (
                  <div
                    key={team.team_id}
                    className="flex items-center justify-between"
                  >
                    <span className="font-medium text-sm">
                      {team.team_name}
                    </span>
                    <span
                      className={cn(
                        "text-xs px-2 py-0.5 rounded font-medium",
                        fdrClass(Math.round(team.fdr_next_6)),
                      )}
                    >
                      {team.fdr_next_6} avg
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>

      {/* Form Watch */}
      <div className="grid gap-6 md:grid-cols-2">
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-green-500" />
            Rising Form
          </h2>
          <Card>
            <CardContent className="pt-4 space-y-2">
              {data.rising_players.map((p) => (
                <div
                  key={p.player_id}
                  className="flex items-center justify-between py-1"
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      className={cn(positionColor(p.position), "text-[10px]")}
                    >
                      {p.position}
                    </Badge>
                    <span className="text-sm font-medium">{p.web_name}</span>
                    <span className="text-xs text-[var(--muted-foreground)]">
                      {p.team_short}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "text-sm font-bold",
                      scoreColor(p.fpl_score),
                    )}
                  >
                    {p.fpl_score.toFixed(1)}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-red-500" />
            Falling Form
          </h2>
          <Card>
            <CardContent className="pt-4 space-y-2">
              {data.falling_players.map((p) => (
                <div
                  key={p.player_id}
                  className="flex items-center justify-between py-1"
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      className={cn(positionColor(p.position), "text-[10px]")}
                    >
                      {p.position}
                    </Badge>
                    <span className="text-sm font-medium">{p.web_name}</span>
                    <span className="text-xs text-[var(--muted-foreground)]">
                      {p.team_short}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "text-sm font-bold",
                      scoreColor(p.fpl_score),
                    )}
                  >
                    {p.fpl_score.toFixed(1)}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      </div>

      {/* Trending Themes */}
      {data.trending_themes.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-2">
            Trending Themes in Media
          </h2>
          <div className="flex gap-2 flex-wrap">
            {data.trending_themes.map((t) => (
              <Badge
                key={t.theme}
                className="bg-[var(--muted)] text-[var(--muted-foreground)]"
              >
                {t.theme} ({t.count})
              </Badge>
            ))}
          </div>
        </section>
      )}

      {/* Navigation links */}
      <div className="grid gap-3 md:grid-cols-4">
        {[
          { to: "/players", label: "Player Rankings", desc: "Full 300-player table" },
          { to: "/fixtures", label: "Fixture Ticker", desc: "FDR heatmap grid" },
          { to: "/transfers", label: "Transfer Hub", desc: "Buy/sell recommendations" },
          { to: "/trends", label: "Trends", desc: "Historical comparison" },
        ].map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className="group rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:shadow-md hover:border-[var(--accent)] transition-all"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">{link.label}</p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {link.desc}
                </p>
              </div>
              <ArrowRight className="h-4 w-4 text-[var(--muted-foreground)] group-hover:text-[var(--accent)] transition-colors" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
