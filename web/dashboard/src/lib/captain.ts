import type { PlayerDashboard } from "@/lib/types";

export interface CaptainCandidate {
  player: PlayerDashboard;
  captainScore: number;
  formNorm: number;
  xgPerNinetyNorm: number;
  fixtureNorm: number;
  pointsNorm: number;
  ownershipNorm: number;
}

export const WEIGHTS = {
  form: 0.3,
  xg: 0.2,
  fixture: 0.2,
  points: 0.15,
  ownership: 0.15,
} as const;

function minMaxNorm(value: number, min: number, max: number): number {
  if (max === min) return 50;
  return ((value - min) / (max - min)) * 100;
}

// Enough minutes to judge a player on. A flat 270 is three full games, which
// nobody has played until late September, so the bar has to move with how much
// football has actually happened — otherwise every candidate is filtered out
// and the page renders empty for the first month of a season. Measure against
// the busiest player so far and cap at the full-season bar.
const FULL_SEASON_MINUTES_BAR = 270;
const ELIGIBLE_MINUTES_SHARE = 0.6;

function eligibleMinutesBar(players: PlayerDashboard[]): number {
  const busiest = Math.max(0, ...players.map((p) => p.minutes));
  return Math.min(FULL_SEASON_MINUTES_BAR, busiest * ELIGIBLE_MINUTES_SHARE);
}

export function computeCandidates(players: PlayerDashboard[]): CaptainCandidate[] {
  const minutesBar = eligibleMinutesBar(players);
  const eligible = players.filter(
    (p) =>
      p.minutes > 0 &&
      p.minutes >= minutesBar &&
      (p.position === "MID" || p.position === "FWD" || p.position === "DEF"),
  );

  if (eligible.length === 0) return [];

  // Derive raw values
  const ppgValues = eligible.map((p) => p.points_per_game);
  const xgPer90Values = eligible.map((p) =>
    p.xg != null && p.minutes > 0 ? (p.xg / p.minutes) * 90 : 0,
  );
  const totalPtsValues = eligible.map((p) => p.total_points);

  const ppgMin = Math.min(...ppgValues);
  const ppgMax = Math.max(...ppgValues);
  const xgMin = Math.min(...xgPer90Values);
  const xgMax = Math.max(...xgPer90Values);
  const ptsMin = Math.min(...totalPtsValues);
  const ptsMax = Math.max(...totalPtsValues);

  return eligible.map((p, idx) => {
    const formNorm = minMaxNorm(p.points_per_game, ppgMin, ppgMax);
    const xgPerNinetyNorm = minMaxNorm(xgPer90Values[idx], xgMin, xgMax);
    const fixtureNorm =
      p.fdr_next_3 != null ? ((5 - p.fdr_next_3) / 4) * 100 : 50;
    const pointsNorm = minMaxNorm(p.total_points, ptsMin, ptsMax);
    const ownershipNorm = Math.min(p.ownership_pct, 100);

    const captainScore =
      formNorm * WEIGHTS.form +
      xgPerNinetyNorm * WEIGHTS.xg +
      fixtureNorm * WEIGHTS.fixture +
      pointsNorm * WEIGHTS.points +
      ownershipNorm * WEIGHTS.ownership;

    return {
      player: p,
      captainScore,
      formNorm,
      xgPerNinetyNorm,
      fixtureNorm,
      pointsNorm,
      ownershipNorm,
    };
  });
}

