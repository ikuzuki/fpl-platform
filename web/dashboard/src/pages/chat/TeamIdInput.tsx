import { useState } from "react";
import { Loader2, UserRound, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { fetchTeam, AgentApiError } from "@/lib/agentApi";
import type { UserSquad } from "@/lib/types";
import { cn } from "@/lib/utils";

const TEAM_ID_KEY = "fpl.teamId";

interface TeamIdInputProps {
  gameweek: number | null; // null = briefing not loaded yet
  squad: UserSquad | null;
  onLoaded: (squad: UserSquad) => void;
  onCleared: () => void;
}

export function TeamIdInput({ gameweek, squad, onLoaded, onCleared }: TeamIdInputProps) {
  const [teamId, setTeamId] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(TEAM_ID_KEY) ?? "";
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLoad() {
    setError(null);
    const id = Number(teamId.trim());
    if (!Number.isInteger(id) || id < 1) {
      setError("Enter a valid FPL team ID (positive integer).");
      return;
    }
    if (gameweek == null) {
      setError("Current gameweek is still loading — try again in a moment.");
      return;
    }
    setLoading(true);
    try {
      const result = await fetchTeam(id, gameweek);
      window.localStorage.setItem(TEAM_ID_KEY, String(id));
      onLoaded(result);
    } catch (e) {
      if (e instanceof AgentApiError) {
        if (e.status === 404) setError(`Team ${id} not found for GW${gameweek}.`);
        else if (e.status === 502) setError("FPL is unreachable right now — try again shortly.");
        else if (e.status === 503) setError("Squad lookup is temporarily disabled.");
        else setError(e.message || `Failed to load team (HTTP ${e.status}).`);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load team.");
      }
    } finally {
      setLoading(false);
    }
  }

  function handleClear() {
    window.localStorage.removeItem(TEAM_ID_KEY);
    setTeamId("");
    setError(null);
    onCleared();
  }

  if (squad) {
    return (
      <Card className="bg-[var(--ai-bg)] border-[var(--ai-border)]">
        <CardContent className="py-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-sm">
            <UserRound className="h-4 w-4 text-[var(--accent)]" />
            <span>
              Loaded team <span className="font-semibold">#{squad.team_id}</span> for GW
              {squad.gameweek}
            </span>
          </div>
          <button
            onClick={handleClear}
            className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] inline-flex items-center gap-1"
          >
            <X className="h-3 w-3" />
            Change team
          </button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="py-4 space-y-3">
        <div>
          <label
            htmlFor="team-id-input"
            className="text-sm font-medium block mb-1"
          >
            Load your squad for personalised advice
          </label>
          <p className="text-xs text-[var(--muted-foreground)]">
            Enter your FPL team ID — find it in the URL of your &ldquo;Pick Team&rdquo;
            page. Optional; you can ask general questions without it.
          </p>
        </div>
        <div className="flex gap-2">
          <input
            id="team-id-input"
            type="text"
            inputMode="numeric"
            placeholder="e.g. 5767400"
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleLoad();
            }}
            disabled={loading}
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] disabled:opacity-50"
          />
          <button
            onClick={handleLoad}
            disabled={loading || !teamId.trim()}
            className={cn(
              "rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-foreground)]",
              "hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed",
              "inline-flex items-center gap-2",
            )}
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Load squad
          </button>
        </div>
        {error && (
          <p role="alert" className="text-xs text-[var(--danger)]">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
