import type {
  PlayerDashboard,
  PlayerHistory,
  FixtureTicker,
  TransferPick,
  TeamStrength,
  GameweekBriefing,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}/${path}`);
  if (!res.ok) throw new Error(`Failed to fetch ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  players: () => fetchJson<PlayerDashboard[]>("player_dashboard.json"),
  fixtures: () => fetchJson<FixtureTicker[]>("fixture_ticker.json"),
  transfers: () => fetchJson<TransferPick[]>("transfer_picks.json"),
  teams: () => fetchJson<TeamStrength[]>("team_strength.json"),
  history: () => fetchJson<PlayerHistory[]>("player_history.json"),
  briefing: () => fetchJson<GameweekBriefing>("gameweek_briefing.json"),
};
