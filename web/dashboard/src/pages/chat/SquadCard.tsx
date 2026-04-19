import { Crown, Star } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatPrice, positionColor } from "@/lib/utils";
import type { SquadPick, UserSquad } from "@/lib/types";

const POSITION_LABEL: Record<number, string> = {
  1: "GKP",
  2: "DEF",
  3: "MID",
  4: "FWD",
};

const POSITION_ORDER = [1, 2, 3, 4] as const;

interface SquadCardProps {
  squad: UserSquad;
  /** Compact mode hides bench + footer for the drawer surface. */
  compact?: boolean;
}

export function SquadCard({ squad, compact = false }: SquadCardProps) {
  const starters = squad.picks.filter((p) => p.position <= 11);
  const bench = squad.picks.filter((p) => p.position > 11);
  const startersByPos = groupByPosition(starters);

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <p className="text-sm font-semibold">
              GW{squad.gameweek} · Team #{squad.team_id}
            </p>
            <p className="text-xs text-[var(--muted-foreground)]">
              {formatPrice(squad.total_value)} squad · {formatPrice(squad.bank)} bank
              {squad.active_chip && ` · chip: ${squad.active_chip}`}
            </p>
          </div>
          {!compact && squad.overall_rank != null && (
            <Badge className="bg-[var(--muted)] text-[var(--foreground)]">
              Rank {new Intl.NumberFormat("en-GB").format(squad.overall_rank)}
            </Badge>
          )}
        </div>

        <div className="space-y-1.5">
          {POSITION_ORDER.map((typeCode) => {
            const row = startersByPos.get(typeCode) ?? [];
            if (row.length === 0) return null;
            return (
              <PickRow
                key={typeCode}
                label={POSITION_LABEL[typeCode]}
                picks={row}
              />
            );
          })}
        </div>

        {!compact && bench.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)] mb-1">
              Bench
            </p>
            <PickRow label="" picks={bench} subtle />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PickRow({
  label,
  picks,
  subtle = false,
}: {
  label: string;
  picks: SquadPick[];
  subtle?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {label && (
        <span
          className={cn(
            "text-[10px] uppercase font-semibold tracking-wide w-9",
            subtle ? "text-[var(--muted-foreground)]" : "text-[var(--muted-foreground)]",
          )}
        >
          {label}
        </span>
      )}
      <div className="flex gap-1.5 flex-wrap flex-1">
        {picks.map((p) => (
          <PickChip key={p.element_id} pick={p} subtle={subtle} />
        ))}
      </div>
    </div>
  );
}

function PickChip({ pick, subtle }: { pick: SquadPick; subtle: boolean }) {
  const posLabel = POSITION_LABEL[pick.element_type] ?? "";
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs",
        subtle
          ? "border-[var(--border)] bg-[var(--background)] opacity-80"
          : "border-[var(--border)] bg-[var(--card)]",
      )}
      title={`${pick.web_name} · ${pick.team_name} · ${formatPrice(pick.price)}`}
    >
      <span className={cn("rounded px-1 py-0.5 text-[10px]", positionColor(posLabel))}>
        {posLabel}
      </span>
      <span className="font-medium">{pick.web_name}</span>
      {pick.is_captain && (
        <Crown
          className="h-3 w-3 text-amber-500"
          aria-label="captain"
        />
      )}
      {pick.is_vice_captain && (
        <Star
          className="h-3 w-3 text-[var(--muted-foreground)]"
          aria-label="vice-captain"
        />
      )}
    </div>
  );
}

function groupByPosition(picks: SquadPick[]): Map<number, SquadPick[]> {
  const map = new Map<number, SquadPick[]>();
  for (const pick of picks) {
    const existing = map.get(pick.element_type);
    if (existing) existing.push(pick);
    else map.set(pick.element_type, [pick]);
  }
  return map;
}
