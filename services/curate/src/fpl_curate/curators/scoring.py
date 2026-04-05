"""Composite FPL score calculation.

Blends form, value, fixtures, xG, ownership momentum, ICT, and injury risk
into a single 0-100 score per player.
"""

import logging

import numpy as np
import pandas as pd

from fpl_curate.config import DEFAULT_FPL_SCORE_WEIGHTS

logger = logging.getLogger(__name__)


def _min_max_scale(series: pd.Series) -> pd.Series:
    """Scale a series to 0-100 using min-max normalisation.

    Returns 50.0 for constant series (all values equal).
    """
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series(50.0, index=series.index)
    return ((series - min_val) / (max_val - min_val)) * 100


def compute_fpl_scores(
    df: pd.DataFrame,
    fixture_fdr: dict[int, dict[str, float]] | None = None,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compute composite FPL scores for a player DataFrame.

    Args:
        df: Player DataFrame with enriched columns.
        fixture_fdr: Mapping of team_id -> {"next_3": avg_fdr, "next_6": avg_fdr}.
        weights: Component weights (must sum to ~1.0). Defaults to config weights.

    Returns:
        DataFrame with added columns: fpl_score, fpl_score_rank, and all component scores.
    """
    w = weights or DEFAULT_FPL_SCORE_WEIGHTS
    fixture_fdr = fixture_fdr or {}
    result = df.copy()

    # --- Component: form (0-100) ---
    result["_c_form"] = _min_max_scale(result["form"].fillna(0))

    # --- Component: value (0-100) ---
    price = result["now_cost"] / 10
    ppm = result["total_points"] / price.replace(0, np.nan)
    result["_c_value"] = _min_max_scale(ppm.fillna(0))

    # --- Component: fixtures (0-100) ---
    # Lower FDR = easier fixtures = higher score. Invert: score = (5 - fdr) / 4 * 100
    result["fdr_next_3"] = result["team"].map(lambda t: fixture_fdr.get(t, {}).get("next_3"))
    result["fdr_next_6"] = result["team"].map(lambda t: fixture_fdr.get(t, {}).get("next_6"))
    fdr_score = (5 - result["fdr_next_3"].fillna(3.0)) / 4 * 100
    result["_c_fixtures"] = fdr_score.clip(0, 100)

    # --- Component: xG overperformance (0-100) ---
    # Prefer Understat xG, fall back to FPL expected_goals
    xg = result["understat_xg"].fillna(result["expected_goals"])
    xg_delta = result["goals_scored"] - xg.fillna(0)
    result["_c_xg_overperformance"] = _min_max_scale(xg_delta.fillna(0))

    # --- Component: ownership momentum (0-100) ---
    net_transfers = result["transfers_in_event"] - result["transfers_out_event"]
    result["_c_ownership_momentum"] = _min_max_scale(net_transfers.fillna(0))

    # --- Component: ICT (0-100) ---
    result["_c_ict"] = _min_max_scale(result["ict_index"].fillna(0))

    # --- Component: injury risk (0-100) ---
    # 0 risk = 100 score, 10 risk = 0 score. Null defaults to 80 (slightly optimistic).
    injury = result.get("injury_signal_risk_score")
    if injury is not None:
        result["_c_injury_risk"] = (100 - injury.fillna(2) * 10).clip(0, 100)
    else:
        result["_c_injury_risk"] = 80.0

    # --- Weighted composite ---
    result["fpl_score"] = (
        w["form"] * result["_c_form"]
        + w["value"] * result["_c_value"]
        + w["fixtures"] * result["_c_fixtures"]
        + w["xg_overperformance"] * result["_c_xg_overperformance"]
        + w["ownership_momentum"] * result["_c_ownership_momentum"]
        + w["ict"] * result["_c_ict"]
        + w["injury_risk"] * result["_c_injury_risk"]
    ).round(1)

    result["fpl_score"] = result["fpl_score"].clip(0, 100)
    result["fpl_score_rank"] = result["fpl_score"].rank(ascending=False, method="min").astype(int)

    # Drop internal component columns
    result = result.drop(columns=[c for c in result.columns if c.startswith("_c_")])

    logger.info(
        "Computed FPL scores: mean=%.1f, median=%.1f, max=%.1f, min=%.1f",
        result["fpl_score"].mean(),
        result["fpl_score"].median(),
        result["fpl_score"].max(),
        result["fpl_score"].min(),
    )

    return result
