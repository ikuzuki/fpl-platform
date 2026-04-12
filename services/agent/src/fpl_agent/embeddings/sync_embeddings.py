"""Sync curated player data + enrichments into Neon pgvector.

Reads from S3 curated layer, generates embeddings, upserts into Neon.
Designed to run after each pipeline execution (triggered by Step Functions).
"""

import logging
import time
from typing import Any

from fpl_agent.embeddings.embedder import PlayerEmbedder
from fpl_lib.clients.neon import NeonClient
from fpl_lib.clients.s3 import S3Client

logger = logging.getLogger(__name__)

UPSERT_QUERY = """
INSERT INTO player_embeddings (
    player_id, season, gameweek, web_name, team_name, position,
    price, total_points, form, goals_scored, assists, minutes,
    summary, form_trend, injury_risk_score, fixture_difficulty,
    embedding, updated_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, NOW())
ON CONFLICT (player_id) DO UPDATE SET
    season = EXCLUDED.season,
    gameweek = EXCLUDED.gameweek,
    web_name = EXCLUDED.web_name,
    team_name = EXCLUDED.team_name,
    position = EXCLUDED.position,
    price = EXCLUDED.price,
    total_points = EXCLUDED.total_points,
    form = EXCLUDED.form,
    goals_scored = EXCLUDED.goals_scored,
    assists = EXCLUDED.assists,
    minutes = EXCLUDED.minutes,
    summary = EXCLUDED.summary,
    form_trend = EXCLUDED.form_trend,
    injury_risk_score = EXCLUDED.injury_risk_score,
    fixture_difficulty = EXCLUDED.fixture_difficulty,
    embedding = EXCLUDED.embedding,
    updated_at = NOW()
"""


async def sync_embeddings(
    s3_client: S3Client,
    neon_client: NeonClient,
    embedder: PlayerEmbedder,
    bucket: str,
    season: str,
    gameweek: int,
) -> dict[str, Any]:
    """Read curated player data from S3, embed, and upsert into Neon.

    Args:
        s3_client: S3 client for reading curated data.
        neon_client: Connected Neon client for upserting embeddings.
        embedder: PlayerEmbedder instance for generating vectors.
        bucket: S3 bucket containing the curated data lake.
        season: Season string, e.g. "2025-26".
        gameweek: Gameweek number.

    Returns:
        Dict with players_synced, embedding_dim, and duration_seconds.
    """
    start = time.time()

    key = (
        f"curated/player_dashboard/season={season}/gameweek={gameweek:02d}/player_dashboard.parquet"
    )
    logger.info("Reading curated data from s3://%s/%s", bucket, key)
    table = s3_client.read_parquet(bucket, key)
    players = table.to_pylist()

    if not players:
        logger.warning("No players found in curated data for %s GW%d", season, gameweek)
        return {
            "players_synced": 0,
            "embedding_dim": PlayerEmbedder.EMBEDDING_DIM,
            "duration_seconds": 0.0,
        }

    logger.info("Building profile texts for %d players", len(players))
    texts = [embedder.build_profile_text(p) for p in players]

    logger.info("Generating embeddings for %d players", len(players))
    embeddings = embedder.embed_batch(texts)

    logger.info("Upserting %d players into Neon", len(players))
    synced = 0
    for player, embedding in zip(players, embeddings, strict=True):
        await neon_client.execute(
            UPSERT_QUERY,
            player.get("player_id", 0),
            season,
            gameweek,
            player.get("web_name", "Unknown"),
            player.get("team_name", "Unknown"),
            player.get("position", "N/A"),
            float(player.get("price", 0.0)),
            int(player.get("total_points", 0)),
            float(player.get("form", 0.0)),
            int(player.get("goals_scored", 0)),
            int(player.get("assists", 0)),
            int(player.get("minutes", 0)),
            player.get("llm_summary"),
            player.get("form_trend"),
            int(player["injury_risk"]) if player.get("injury_risk") is not None else None,
            float(player["fdr_next_3"]) if player.get("fdr_next_3") is not None else None,
            embedding,
        )
        synced += 1

    duration = round(time.time() - start, 2)
    logger.info("Synced %d players in %.2fs", synced, duration)

    return {
        "players_synced": synced,
        "embedding_dim": PlayerEmbedder.EMBEDDING_DIM,
        "duration_seconds": duration,
    }
