import {
  AlertTriangle,
  Check,
  CircleAlert,
  Database,
  Trophy,
  X as XIcon,
} from "lucide-react";
import type { ComponentType, SVGProps } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatPrice, positionColor } from "@/lib/utils";
import type { AgentResponse, FixtureOutlook, PlayerAnalysis } from "@/lib/types";

const OUTLOOK_STYLES: Record<FixtureOutlook, string> = {
  green: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  amber: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  red: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

const OUTLOOK_LABELS: Record<FixtureOutlook, string> = {
  green: "Easy fixtures",
  amber: "Mixed fixtures",
  red: "Tough fixtures",
};

// Colour alone is not WCAG-friendly; pair every outlook with a glyph so
// the signal survives colourblindness or a monochrome screenshot.
const OUTLOOK_ICONS: Record<FixtureOutlook, ComponentType<SVGProps<SVGSVGElement>>> = {
  green: Check,
  amber: CircleAlert,
  red: XIcon,
};

interface ScoutReportCardProps {
  response: AgentResponse;
  /** Compact mode tightens spacing for the drawer surface. */
  compact?: boolean;
}

export function ScoutReportCard({ response, compact = false }: ScoutReportCardProps) {
  const { report, iterations_used, tool_calls_made } = response;

  return (
    <Card className="border-l-4 border-l-[var(--accent)]">
      <CardContent className={cn("space-y-4", compact ? "py-3" : "py-4")}>
        <p className="leading-relaxed whitespace-pre-wrap">{report.analysis}</p>

        {report.players.length > 0 && (
          <div className={cn("grid gap-2", compact ? "grid-cols-1" : "sm:grid-cols-2")}>
            {report.players.map((player) => (
              <PlayerMiniCard key={player.player_name} player={player} />
            ))}
          </div>
        )}

        {report.comparison && (
          <Card className="bg-[var(--muted)]/40">
            <CardContent className="py-3 space-y-1">
              <div className="flex items-center gap-2">
                <Trophy className="h-4 w-4 text-[var(--accent)]" />
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                  Head to head
                </span>
                {report.comparison.winner && (
                  <Badge className="bg-[var(--ai-bg)] text-[var(--accent)] border border-[var(--ai-border)]">
                    Pick: {report.comparison.winner}
                  </Badge>
                )}
              </div>
              <p className="text-sm leading-relaxed">
                {report.comparison.reasoning}
              </p>
            </CardContent>
          </Card>
        )}

        <div className="rounded-md bg-[var(--ai-bg)] border border-[var(--ai-border)] p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--accent)] mb-1">
            Recommendation
          </p>
          <p className="text-sm font-medium leading-snug">{report.recommendation}</p>
        </div>

        {report.caveats.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                Caveats
              </span>
            </div>
            <ul className="text-xs text-[var(--muted-foreground)] space-y-0.5 list-disc list-inside">
              {report.caveats.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="pt-2 border-t border-[var(--border)] flex items-center justify-between text-[11px] text-[var(--muted-foreground)] flex-wrap gap-2">
          <span className="inline-flex items-center gap-1">
            <Database className="h-3 w-3" />
            {report.data_sources.length > 0
              ? `Sources: ${report.data_sources.join(", ")}`
              : "No data sources recorded"}
          </span>
          <span>
            {iterations_used} iteration{iterations_used === 1 ? "" : "s"} ·{" "}
            {tool_calls_made.length} tool call{tool_calls_made.length === 1 ? "" : "s"}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function PlayerMiniCard({ player }: { player: PlayerAnalysis }) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3 space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold truncate">{player.player_name}</p>
          <p className="text-[11px] text-[var(--muted-foreground)]">
            {formatPrice(player.price)} · form {player.form.toFixed(1)}
          </p>
        </div>
        <Badge className={positionColor(player.position)}>{player.position}</Badge>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <Badge
          className={cn("inline-flex items-center gap-1", OUTLOOK_STYLES[player.fixture_outlook])}
        >
          {(() => {
            const Icon = OUTLOOK_ICONS[player.fixture_outlook];
            return <Icon className="h-3 w-3" aria-hidden="true" />;
          })()}
          {OUTLOOK_LABELS[player.fixture_outlook]}
        </Badge>
        <span className="text-[11px] text-[var(--muted-foreground)]">
          confidence {Math.round(player.confidence * 100)}%
        </span>
      </div>
      <p className="text-sm leading-snug">{player.verdict}</p>
    </div>
  );
}
