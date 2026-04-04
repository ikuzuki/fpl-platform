-- Initialize FPL live match database
CREATE TABLE IF NOT EXISTS live_scores (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL,
    gameweek INTEGER NOT NULL,
    fixture_id INTEGER NOT NULL,
    minutes INTEGER DEFAULT 0,
    goals_scored INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    clean_sheets INTEGER DEFAULT 0,
    bonus INTEGER DEFAULT 0,
    total_points INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, gameweek, fixture_id)
);

CREATE INDEX idx_live_scores_gameweek ON live_scores(gameweek);
CREATE INDEX idx_live_scores_player ON live_scores(player_id);
