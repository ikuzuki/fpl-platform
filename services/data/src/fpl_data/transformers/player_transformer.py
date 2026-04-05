"""Transform raw FPL bootstrap data into clean Parquet format."""

import logging
import unicodedata
from datetime import UTC, datetime
from typing import Any

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


def _normalise_name(name: str) -> str:
    """Normalise a player name for fuzzy matching.

    Strips accents, lowercases, and removes hyphens/apostrophes.
    """
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_name.lower().replace("-", " ").replace("'", "").strip()


# Understat columns to join into clean player data
UNDERSTAT_COLUMNS = ["xG", "xA", "npxG", "npg", "shots", "key_passes", "xGChain", "xGBuildup"]
UNDERSTAT_RENAME = {
    "xG": "understat_xg",
    "xA": "understat_xa",
    "npxG": "understat_npxg",
    "npg": "understat_npg",
    "shots": "understat_shots",
    "key_passes": "understat_key_passes",
    "xGChain": "understat_xg_chain",
    "xGBuildup": "understat_xg_buildup",
}


def join_understat(df: pd.DataFrame, understat_data: list[dict[str, Any]]) -> pd.DataFrame:
    """Join Understat xG/xA stats into the clean player DataFrame.

    Matches on normalised full name (first_name + second_name) against
    Understat player_name. Falls back to web_name match.

    Args:
        df: Clean FPL player DataFrame (must have first_name, second_name, web_name).
        understat_data: Raw Understat league stats list of dicts.

    Returns:
        DataFrame with Understat columns added (NaN for unmatched players).
    """
    if not understat_data:
        logger.warning("No Understat data to join — skipping")
        return df

    us_df = pd.DataFrame(understat_data)

    # Cast Understat numeric strings to float
    for col in UNDERSTAT_COLUMNS:
        if col in us_df.columns:
            us_df[col] = pd.to_numeric(us_df[col], errors="coerce")

    # Build normalised name lookup from Understat
    us_df["_us_name_norm"] = us_df["player_name"].apply(_normalise_name)

    # Build normalised names from FPL
    df["_fpl_full_norm"] = (df["first_name"] + " " + df["second_name"]).apply(_normalise_name)
    df["_fpl_web_norm"] = df["web_name"].apply(_normalise_name)

    # Merge on full name first
    us_lookup = us_df.set_index("_us_name_norm")[UNDERSTAT_COLUMNS]
    us_lookup = us_lookup[~us_lookup.index.duplicated(keep="first")]

    merged = df.join(us_lookup, on="_fpl_full_norm", how="left")

    # Fall back to web_name for unmatched rows
    unmatched = merged[UNDERSTAT_COLUMNS[0]].isna()
    if unmatched.any():
        fallback = df.loc[unmatched, "_fpl_web_norm"]
        for idx, web_norm in fallback.items():
            if web_norm in us_lookup.index:
                for col in UNDERSTAT_COLUMNS:
                    merged.at[idx, col] = us_lookup.at[web_norm, col]

    # Rename to understat_ prefixed columns
    merged = merged.rename(columns=UNDERSTAT_RENAME)

    matched = merged["understat_xg"].notna().sum()
    logger.info(
        "Understat join: %d/%d players matched (%.0f%%)",
        matched,
        len(df),
        100 * matched / len(df) if len(df) > 0 else 0,
    )

    # Clean up temp columns
    merged = merged.drop(columns=["_fpl_full_norm", "_fpl_web_norm"])

    return merged


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
