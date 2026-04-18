"""Player dashboard curator — builds the main player fact table."""

import logging
from typing import Any

import pandas as pd

from fpl_curate.config import POSITION_MAP
from fpl_curate.curators.scoring import compute_fpl_scores

logger = logging.getLogger(__name__)


def build_player_dashboard(
    enriched_df: pd.DataFrame,
    team_map: dict[int, dict[str, str]],
    fixture_fdr: dict[int, dict[str, float]],
    weights: dict[str, float] | None,
    season: str,
    gameweek: int,
    advice_gameweek: int | None = None,
) -> list[dict[str, Any]]:
    """Build the player dashboard curated dataset.

    Args:
        enriched_df: Full enriched player DataFrame (825 rows, 56 cols).
        team_map: Team ID -> {"name", "short_name"} mapping.
        fixture_fdr: Team ID -> {"next_3", "next_6"} FDR averages.
        weights: FPL score component weights.
        season: Season identifier.
        gameweek: Gameweek the underlying data was collected for (finished GW).
        advice_gameweek: Gameweek this dashboard advises on — typically
            ``gameweek + 1``. ``None`` at end-of-season. The Captain Picker UI
            renders this instead of ``gameweek``.

    Returns:
        List of dicts ready for Pydantic validation / Parquet write.
    """
    df = enriched_df.copy()

    # Filter to enriched players only (top 300 by ownership that have LLM data)
    df = df[df["player_summary_summary"].notna()].copy()
    logger.info("Filtered to %d enriched players", len(df))

    # Compute FPL scores (adds fpl_score, fpl_score_rank, fdr_next_3, fdr_next_6)
    df = compute_fpl_scores(df, fixture_fdr=fixture_fdr, weights=weights)

    # Derive fields
    price = df["now_cost"] / 10
    df["price"] = price.round(1)
    df["points_per_million"] = (df["total_points"] / price.replace(0, float("nan"))).round(1)
    df["net_transfers"] = df["transfers_in_event"] - df["transfers_out_event"]

    # xG delta: prefer Understat, fall back to FPL expected_goals
    xg = df["understat_xg"].fillna(df["expected_goals"])
    df["xg_delta"] = (df["goals_scored"] - xg).where(xg.notna())

    # Map team and position
    df["team_name"] = df["team"].map(lambda t: team_map.get(t, {}).get("name", f"Team {t}"))
    df["team_short"] = df["team"].map(lambda t: team_map.get(t, {}).get("short_name", "???"))
    df["position"] = df["element_type"].map(POSITION_MAP)
    df["full_name"] = df["first_name"] + " " + df["second_name"]

    # Build output rows
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "player_id": int(row["id"]),
                "web_name": row["web_name"],
                "full_name": row["full_name"],
                "team_name": row["team_name"],
                "team_short": row["team_short"],
                "position": row["position"],
                # Performance
                "total_points": int(row["total_points"]),
                "minutes": int(row["minutes"]),
                "goals_scored": int(row["goals_scored"]),
                "assists": int(row["assists"]),
                "clean_sheets": int(row["clean_sheets"]),
                "bonus": int(row["bonus"]),
                "form": float(row["form"]),
                "points_per_game": float(row["points_per_game"]),
                # Value
                "price": float(row["price"]),
                "ownership_pct": float(row["selected_by_percent"]),
                "points_per_million": float(row["points_per_million"])
                if pd.notna(row["points_per_million"])
                else 0.0,
                "transfers_in": int(row["transfers_in_event"]),
                "transfers_out": int(row["transfers_out_event"]),
                "net_transfers": int(row["net_transfers"]),
                # xStats
                "xg": _safe_float(row.get("understat_xg")),
                "xa": _safe_float(row.get("understat_xa")),
                "npxg": _safe_float(row.get("understat_npxg")),
                "xg_delta": _safe_float(row.get("xg_delta")),
                # ICT
                "influence": float(row["influence"]),
                "creativity": float(row["creativity"]),
                "threat": float(row["threat"]),
                "ict_index": float(row["ict_index"]),
                # LLM enrichments
                "form_trend": row.get("player_summary_form_trend"),
                "form_confidence": _safe_float(row.get("player_summary_confidence")),
                "llm_summary": row.get("player_summary_summary"),
                "injury_risk": _safe_int(row.get("injury_signal_risk_score")),
                "injury_reasoning": row.get("injury_signal_reasoning"),
                "sentiment_label": row.get("sentiment_sentiment"),
                "sentiment_score": _safe_float(row.get("sentiment_score")),
                "key_themes": _safe_list(row.get("sentiment_key_themes")),
                # Fixtures
                "fdr_next_3": _safe_float(row.get("fdr_next_3")),
                "fdr_next_6": _safe_float(row.get("fdr_next_6")),
                "best_gameweeks": _safe_list(row.get("fixture_outlook_best_gameweeks")),
                "fixture_recommendation": row.get("fixture_outlook_recommendation"),
                # Composite
                "fpl_score": float(row["fpl_score"]),
                "fpl_score_rank": int(row["fpl_score_rank"]),
                # Score components (weighted contributions)
                "score_form": _safe_float(row.get("score_form")),
                "score_value": _safe_float(row.get("score_value")),
                "score_fixtures": _safe_float(row.get("score_fixtures")),
                "score_xg": _safe_float(row.get("score_xg")),
                "score_momentum": _safe_float(row.get("score_momentum")),
                "score_ict": _safe_float(row.get("score_ict")),
                "score_injury": _safe_float(row.get("score_injury")),
                # Partition
                "season": season,
                "gameweek": gameweek,
                "advice_gameweek": advice_gameweek,
            }
        )

    logger.info("Built player dashboard: %d rows", len(rows))
    return rows


def _safe_float(val: Any) -> float | None:
    """Convert to float, returning None for NaN/None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return float(val)


def _safe_int(val: Any) -> int | None:
    """Convert to int, returning None for NaN/None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return int(val)


def _safe_list(val: Any) -> list[Any] | None:
    """Convert numpy array or list to Python list, returning None for null."""
    if val is None:
        return None
    try:
        return list(val)
    except (TypeError, ValueError):
        return None
