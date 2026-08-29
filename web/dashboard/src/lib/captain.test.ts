import { describe, it, expect } from "vitest";
import type { PlayerDashboard } from "@/lib/types";
import { computeCandidates } from "./captain";

function player(overrides: Partial<PlayerDashboard>): PlayerDashboard {
  return {
    player_id: 1,
    web_name: "Test",
    full_name: "Test Player",
    team_name: "Test FC",
    team_short: "TST",
    position: "MID",
    total_points: 20,
    minutes: 180,
    goals_scored: 2,
    assists: 1,
    clean_sheets: 0,
    bonus: 3,
    form: 5,
    points_per_game: 5,
    price: 7.5,
    ownership_pct: 12,
    points_per_million: 2.6,
    transfers_in: 0,
    transfers_out: 0,
    net_transfers: 0,
    xg: 1.4,
    xa: 0.6,
    npxg: 1.4,
    xg_delta: 0.2,
    influence: 40,
    creativity: 30,
    threat: 50,
    ict_index: 12,
    form_trend: null,
    form_confidence: null,
    llm_summary: null,
    injury_risk: null,
    injury_reasoning: null,
    sentiment_label: null,
    sentiment_score: null,
    key_themes: null,
    fdr_next_3: 3,
    fdr_next_6: 3,
    best_gameweeks: null,
    fixture_recommendation: null,
    fpl_score: 60,
    fpl_score_rank: 1,
    score_form: null,
    score_value: null,
    ...overrides,
  } as PlayerDashboard;
}

describe("computeCandidates", () => {
  it("ranks players early in a season, when nobody has three full games yet", () => {
    // Two rounds played: the old flat 270-minute bar excluded everyone and the
    // page rendered blank until late September.
    const players = [
      player({ player_id: 1, web_name: "Starter", minutes: 180 }),
      player({ player_id: 2, web_name: "Regular", minutes: 160 }),
      player({ player_id: 3, web_name: "Benchwarmer", minutes: 20 }),
    ];

    const names = computeCandidates(players).map((c) => c.player.web_name);

    expect(names).toContain("Starter");
    expect(names).toContain("Regular");
    expect(names).not.toContain("Benchwarmer");
  });

  it("holds the full-season bar at 270 minutes once enough football is played", () => {
    const players = [
      player({ player_id: 1, web_name: "Ever-present", minutes: 3000 }),
      player({ player_id: 2, web_name: "Squad player", minutes: 300 }),
      player({ player_id: 3, web_name: "Fringe", minutes: 200 }),
    ];

    const names = computeCandidates(players).map((c) => c.player.web_name);

    // 60% of 3000 would be 1800; the cap keeps the squad player eligible.
    expect(names).toContain("Squad player");
    expect(names).not.toContain("Fringe");
  });

  it("returns nothing before a ball is kicked rather than ranking on zero minutes", () => {
    const players = [
      player({ player_id: 1, minutes: 0 }),
      player({ player_id: 2, minutes: 0 }),
    ];

    expect(computeCandidates(players)).toEqual([]);
  });

  it("excludes goalkeepers", () => {
    const players = [
      player({ player_id: 1, web_name: "Keeper", position: "GKP", minutes: 180 }),
      player({ player_id: 2, web_name: "Forward", position: "FWD", minutes: 180 }),
    ];

    const names = computeCandidates(players).map((c) => c.player.web_name);

    expect(names).toEqual(["Forward"]);
  });
});
