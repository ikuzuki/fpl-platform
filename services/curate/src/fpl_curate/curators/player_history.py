"""Player history curator — maintains an append-only history of player metrics per gameweek.

Uses upsert-by-gameweek semantics: running the same gameweek twice replaces that
gameweek's rows (idempotent). Running an older gameweek inserts it in order.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Subset of fields to track per gameweek (keeps the file small)
HISTORY_FIELDS = [
    "player_id",
    "web_name",
    "team_short",
    "position",
    "gameweek",
    "season",
    "total_points",
    "form",
    "price",
    "ownership_pct",
    "fpl_score",
    "fpl_score_rank",
    "form_trend",
    "injury_risk",
    "sentiment_score",
    "fdr_next_3",
    "net_transfers",
    "points_per_million",
]


def build_player_history(
    dashboard_rows: list[dict[str, Any]],
    existing_history: list[dict[str, Any]],
    season: str,
    gameweek: int,
) -> list[dict[str, Any]]:
    """Build updated player history by upserting the current gameweek.

    Args:
        dashboard_rows: Current gameweek's player dashboard output.
        existing_history: Previously accumulated history (may be empty).
        season: Season identifier.
        gameweek: Current gameweek number.

    Returns:
        Full history list sorted by (gameweek, player_id).
    """
    # Extract slim history rows from current gameweek
    new_rows = []
    for player in dashboard_rows:
        row = {field: player.get(field) for field in HISTORY_FIELDS}
        row["season"] = season
        row["gameweek"] = gameweek
        new_rows.append(row)

    # Remove existing rows for this gameweek (upsert semantics)
    history = [
        row
        for row in existing_history
        if not (row.get("gameweek") == gameweek and row.get("season") == season)
    ]

    # Append new rows
    history.extend(new_rows)

    # Sort by gameweek then player_id for consistent ordering
    history.sort(key=lambda r: (r.get("gameweek", 0), r.get("player_id", 0)))

    logger.info(
        "Built player history: %d total rows (%d gameweeks, %d new rows for GW%d)",
        len(history),
        len({r.get("gameweek") for r in history}),
        len(new_rows),
        gameweek,
    )

    return history
