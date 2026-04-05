export interface PlayerDashboard {
  player_id: number;
  web_name: string;
  full_name: string;
  team_name: string;
  team_short: string;
  position: string;
  total_points: number;
  minutes: number;
  goals_scored: number;
  assists: number;
  clean_sheets: number;
  bonus: number;
  form: number;
  points_per_game: number;
  price: number;
  ownership_pct: number;
  points_per_million: number;
  transfers_in: number;
  transfers_out: number;
  net_transfers: number;
  xg: number | null;
  xa: number | null;
  npxg: number | null;
  xg_delta: number | null;
  influence: number;
  creativity: number;
  threat: number;
  ict_index: number;
  form_trend: string | null;
  form_confidence: number | null;
  llm_summary: string | null;
  injury_risk: number | null;
  injury_reasoning: string | null;
  sentiment_label: string | null;
  sentiment_score: number | null;
  key_themes: string[] | null;
  fdr_next_3: number | null;
  fdr_next_6: number | null;
  best_gameweeks: number[] | null;
  fixture_recommendation: string | null;
  fpl_score: number;
  fpl_score_rank: number;
  score_form: number | null;
  score_value: number | null;
  score_fixtures: number | null;
  score_xg: number | null;
  score_momentum: number | null;
  score_ict: number | null;
  score_injury: number | null;
  season: string;
  gameweek: number;
}

export interface BriefingPick {
  player_id: number;
  web_name: string;
  team_short: string;
  position: string;
  price: number;
  fpl_score: number;
  form: number;
  reasons: string[];
  llm_summary: string | null;
}

export interface BriefingAlert {
  player_id: number;
  web_name: string;
  team_short: string;
  position: string;
  injury_risk: number;
  injury_reasoning: string | null;
}

export interface BriefingFixture {
  team_id: number;
  team_name: string;
  team_short: string;
  fdr_next_3: number;
  fdr_next_6: number;
}

export interface GameweekBriefing {
  season: string;
  gameweek: number;
  top_picks: BriefingPick[];
  sell_alerts: { player_id: number; web_name: string; team_short: string; position: string; fpl_score: number; reasons: string[] }[];
  injury_alerts: BriefingAlert[];
  best_fixtures: BriefingFixture[];
  worst_fixtures: BriefingFixture[];
  rising_players: { player_id: number; web_name: string; team_short: string; position: string; form: number; fpl_score: number }[];
  falling_players: { player_id: number; web_name: string; team_short: string; position: string; form: number; fpl_score: number }[];
  trending_themes: { theme: string; count: number }[];
  summary_stats: {
    total_players: number;
    buy_count: number;
    sell_count: number;
    injury_count: number;
    improving_count: number;
    declining_count: number;
  };
}

export interface FixtureTicker {
  team_id: number;
  team_name: string;
  team_short: string;
  gameweek: number;
  opponent: string;
  opponent_short: string;
  is_home: boolean;
  fdr: number;
  kickoff_time: string | null;
  season: string;
}

export interface TransferPick {
  player_id: number;
  web_name: string;
  team_name: string;
  team_short: string;
  position: string;
  price: number;
  fpl_score: number;
  fpl_score_rank: number;
  recommendation: "buy" | "sell" | "hold" | "watch";
  recommendation_reasons: string[];
  form: number;
  form_trend: string | null;
  injury_risk: number | null;
  fdr_next_3: number | null;
  net_transfers: number;
  season: string;
  gameweek: number;
}

export interface PlayerHistory {
  player_id: number;
  web_name: string;
  team_short: string;
  position: string;
  gameweek: number;
  season: string;
  total_points: number;
  form: number;
  price: number;
  ownership_pct: number;
  fpl_score: number;
  fpl_score_rank: number;
  form_trend: string | null;
  injury_risk: number | null;
  sentiment_score: number | null;
  fdr_next_3: number | null;
  net_transfers: number;
  points_per_million: number;
}

export interface TeamStrength {
  team_id: number;
  team_name: string;
  team_short: string;
  avg_fpl_score: number;
  total_points: number;
  avg_form: number;
  squad_value: number;
  top_scorer_id: number;
  top_scorer_name: string;
  top_scorer_points: number;
  avg_fdr_remaining: number | null;
  player_count: number;
  enriched_player_count: number;
  season: string;
  gameweek: number;
}
