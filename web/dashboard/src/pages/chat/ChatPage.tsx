import { useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { GameweekBriefing, UserSquad } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { SquadCard } from "./SquadCard";
import { TeamIdInput } from "./TeamIdInput";

export function ChatPage() {
  const { data: briefing } = useApi(
    () => api.briefing(),
    null as GameweekBriefing | null,
  );
  const [squad, setSquad] = useState<UserSquad | null>(null);

  // Squad lookup needs the *current* gameweek so we ask about the right
  // squad snapshot. Fall back to null while briefing is loading; the
  // input component shows an inline message instead of erroring.
  const currentGw = briefing?.gameweek ?? null;

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <ScoutHero />

      <TeamIdInput
        gameweek={currentGw}
        squad={squad}
        onLoaded={setSquad}
        onCleared={() => setSquad(null)}
      />

      {squad && <SquadCard squad={squad} />}

      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-sm p-4">
        <ChatPanel squad={squad} />
      </div>
    </div>
  );
}

function ScoutHero() {
  return (
    <div className="rounded-xl border border-[var(--ai-border)] bg-gradient-to-br from-[var(--ai-bg)] to-[var(--card)] p-6">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--accent-foreground)] shrink-0">
          <Sparkles className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Scout</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-1 leading-relaxed">
            Ask anything about your FPL team — captain picks, transfer ideas,
            differentials, fixture swings. Load your team ID for personalised
            advice, or just ask a general question.
          </p>
        </div>
      </div>
    </div>
  );
}
