"""Transform raw FPL bootstrap data into clean Parquet format."""

import logging
from datetime import UTC, datetime

import pandas as pd

logger = logging.getLogger(__name__)

# Columns to extract from raw bootstrap elements, mapped to clean snake_case names
COLUMN_MAP: dict[str, str] = {
    "id": "id",
    "web_name": "web_name",
    "first_name": "first_name",
    "second_name": "second_name",
    "team": "team",
    "element_type": "element_type",
    "now_cost": "now_cost",
    "total_points": "total_points",
    "minutes": "minutes",
    "goals_scored": "goals_scored",
    "assists": "assists",
    "clean_sheets": "clean_sheets",
    "goals_conceded": "goals_conceded",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
    "bonus": "bonus",
    "bps": "bps",
    "starts": "starts",
    "expected_goals": "expected_goals",
    "expected_assists": "expected_assists",
    "expected_goal_involvements": "expected_goal_involvements",
    "form": "form",
    "points_per_game": "points_per_game",
    "selected_by_percent": "selected_by_percent",
    "status": "status",
    "news": "news",
    "chance_of_playing_next_round": "chance_of_playing_next_round",
    "transfers_in_event": "transfers_in_event",
    "transfers_out_event": "transfers_out_event",
    "influence": "influence",
    "creativity": "creativity",
    "threat": "threat",
    "ict_index": "ict_index",
}

INT_COLUMNS = [
    "id",
    "team",
    "element_type",
    "now_cost",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "yellow_cards",
    "red_cards",
    "bonus",
    "bps",
    "starts",
    "transfers_in_event",
    "transfers_out_event",
]

FLOAT_COLUMNS = [
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "form",
    "points_per_game",
    "selected_by_percent",
    "influence",
    "creativity",
    "threat",
    "ict_index",
]


def flatten_player_data(raw: dict, season: str) -> pd.DataFrame:
    """Flatten raw FPL bootstrap response into a clean DataFrame.

    Args:
        raw: Raw bootstrap-static API response dict.
        season: Season identifier to add as a column.

    Returns:
        DataFrame with selected and typed columns.
    """
    elements = raw.get("elements", [])
    if not elements:
        return pd.DataFrame()

    df = pd.DataFrame(elements)

    # Warn about unexpected new columns
    expected = set(COLUMN_MAP.keys())
    actual = set(df.columns)
    new_cols = actual - expected - {"code", "photo", "squad_number", "special", "removed"}
    if new_cols:
        logger.warning("New unexpected columns in raw data: %s", sorted(new_cols))

    # Select and rename columns
    available = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df[list(available.keys())].rename(columns=available)

    # Cast types
    for col in INT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in FLOAT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Float64")

    # Add metadata columns
    df["season"] = season
    df["collected_at"] = datetime.now(UTC).isoformat()

    return df


def deduplicate(df: pd.DataFrame, key_columns: list[str]) -> pd.DataFrame:
    """Remove duplicate rows based on key columns, keeping the last occurrence.

    Args:
        df: Input DataFrame.
        key_columns: Columns to check for duplicates.

    Returns:
        Deduplicated DataFrame.
    """
    before = len(df)
    df = df.drop_duplicates(subset=key_columns, keep="last")
    after = len(df)
    if before != after:
        logger.info("Deduplicated: %d → %d rows (removed %d)", before, after, before - after)
    return df
