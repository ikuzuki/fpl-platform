-- Player embeddings schema for Neon pgvector.
-- Apply manually to a fresh Neon database before running the sync handler.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS player_embeddings (
    player_id          INTEGER PRIMARY KEY,
    season             VARCHAR(10) NOT NULL,
    gameweek           INTEGER NOT NULL,
    web_name           VARCHAR(100) NOT NULL,
    team_name          VARCHAR(100) NOT NULL,
    position           VARCHAR(3) NOT NULL,
    price              REAL NOT NULL,
    total_points       INTEGER NOT NULL,
    form               REAL NOT NULL,
    goals_scored       INTEGER NOT NULL,
    assists            INTEGER NOT NULL,
    minutes            INTEGER NOT NULL,
    summary            TEXT,
    form_trend         VARCHAR(20),
    injury_risk_score  INTEGER,
    fixture_difficulty REAL,
    embedding          vector(384) NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- IVFFlat index for approximate nearest-neighbour vector search.
-- lists = ~sqrt(expected_rows) ≈ sqrt(300) ≈ 20.
CREATE INDEX IF NOT EXISTS idx_player_embeddings_vector
    ON player_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 20);

-- Filtering indexes for structured queries.
CREATE INDEX IF NOT EXISTS idx_player_embeddings_position ON player_embeddings (position);
CREATE INDEX IF NOT EXISTS idx_player_embeddings_team ON player_embeddings (team_name);
CREATE INDEX IF NOT EXISTS idx_player_embeddings_price ON player_embeddings (price);
