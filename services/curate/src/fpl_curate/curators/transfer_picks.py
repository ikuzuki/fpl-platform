"""Transfer picks curator — derives buy/sell/hold/watch recommendations."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_transfer_picks(
    dashboard_rows: list[dict[str, Any]],
    season: str,
    gameweek: int,
) -> list[dict[str, Any]]:
    """Build transfer recommendation rows from player dashboard data.

    Args:
        dashboard_rows: Output from build_player_dashboard.
        season: Season identifier.
        gameweek: Current gameweek number.

    Returns:
        List of dicts with recommendation and reasoning per player.
    """
    rows: list[dict[str, Any]] = []

    for player in dashboard_rows:
        recommendation, reasons = _classify_player(player)

        rows.append({
            "player_id": player["player_id"],
            "web_name": player["web_name"],
            "team_name": player["team_name"],
            "team_short": player["team_short"],
            "position": player["position"],
            "price": player["price"],
            "fpl_score": player["fpl_score"],
            "fpl_score_rank": player["fpl_score_rank"],
            "recommendation": recommendation,
            "recommendation_reasons": reasons,
            "form": player["form"],
            "form_trend": player.get("form_trend"),
            "injury_risk": player.get("injury_risk"),
            "fdr_next_3": player.get("fdr_next_3"),
            "net_transfers": player["net_transfers"],
            "season": season,
            "gameweek": gameweek,
        })

    buy_count = sum(1 for r in rows if r["recommendation"] == "buy")
    sell_count = sum(1 for r in rows if r["recommendation"] == "sell")
    logger.info(
        "Built transfer picks: %d total, %d buy, %d sell",
        len(rows), buy_count, sell_count,
    )

    return rows


def _classify_player(player: dict[str, Any]) -> tuple[str, list[str]]:
    """Classify a player as buy/sell/hold/watch with reasoning.

    Returns:
        Tuple of (recommendation, list_of_reasons).
    """
    score = player["fpl_score"]
    form = player["form"]
    fdr = player.get("fdr_next_3")
    injury = player.get("injury_risk")
    net_transfers = player["net_transfers"]
    form_trend = player.get("form_trend")
    ppm = player.get("points_per_million", 0)

    reasons: list[str] = []

    # --- Sell signals ---
    sell_signals = 0
    if injury is not None and injury >= 8:
        reasons.append(f"High injury risk ({injury}/10)")
        sell_signals += 2
    if form < 2.0:
        reasons.append(f"Poor form ({form})")
        sell_signals += 1
    if form_trend == "declining":
        reasons.append("Declining form trend")
        sell_signals += 1
    if fdr is not None and fdr >= 4.0:
        reasons.append(f"Very hard fixtures (FDR {fdr:.1f})")
        sell_signals += 1
    if score < 30:
        reasons.append(f"Low FPL score ({score})")
        sell_signals += 1

    if sell_signals >= 2 or score < 25:
        return "sell", reasons

    # --- Buy signals ---
    buy_signals = 0
    buy_reasons: list[str] = []
    if score >= 65:
        buy_reasons.append(f"Strong FPL score ({score})")
        buy_signals += 1
    if form >= 5.0:
        buy_reasons.append(f"Good form ({form})")
        buy_signals += 1
    if form_trend == "improving":
        buy_reasons.append("Improving form trend")
        buy_signals += 1
    if fdr is not None and fdr <= 2.5:
        buy_reasons.append(f"Favorable fixtures (FDR {fdr:.1f})")
        buy_signals += 1
    if injury is not None and injury <= 1:
        buy_reasons.append("Minimal injury risk")
        buy_signals += 1
    if ppm >= 5.0:
        buy_reasons.append(f"Great value ({ppm:.1f} pts/£m)")
        buy_signals += 1

    if buy_signals >= 3:
        return "buy", buy_reasons

    # --- Watch signals ---
    if buy_signals >= 2 or (score >= 55 and net_transfers > 10000):
        watch_reasons = buy_reasons or reasons
        if net_transfers > 10000:
            watch_reasons.append(f"High transfer demand (+{net_transfers:,})")
        return "watch", watch_reasons

    # --- Hold ---
    if not reasons:
        reasons.append(f"FPL score {score} — no strong signals")
    return "hold", reasons
