"""Gameweek briefing curator — aggregates top signals into a structured weekly briefing.

No LLM call needed — all fields are derived from existing enrichment data.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_gameweek_briefing(
    dashboard_rows: list[dict[str, Any]],
    transfer_rows: list[dict[str, Any]],
    fixture_fdr: dict[int, dict[str, float]],
    team_map: dict[int, dict[str, str]],
    season: str,
    gameweek: int,
    advice_gameweek: int | None = None,
) -> dict[str, Any]:
    """Build a gameweek briefing from existing curated data.

    Args:
        dashboard_rows: Player dashboard output (300 players).
        transfer_rows: Transfer picks output.
        fixture_fdr: Team ID -> {"next_3", "next_6"} FDR averages.
        team_map: Team ID -> {"name", "short_name"} mapping.
        season: Season identifier.
        gameweek: Gameweek the underlying data was collected for (finished GW).
        advice_gameweek: Gameweek this briefing gives advice for — typically
            ``gameweek + 1``. ``None`` at end-of-season. UI renders this as the
            page label so users see next-GW advice.

    Returns:
        Structured briefing dict for JSON serialisation.
    """
    # Top buy picks (highest fpl_score with buy recommendation)
    buys = [t for t in transfer_rows if t["recommendation"] == "buy"]
    buys.sort(key=lambda x: -x["fpl_score"])
    top_picks = []
    for pick in buys[:3]:
        player = next(
            (p for p in dashboard_rows if p["player_id"] == pick["player_id"]),
            None,
        )
        top_picks.append(
            {
                "player_id": pick["player_id"],
                "web_name": pick["web_name"],
                "team_short": pick["team_short"],
                "position": pick["position"],
                "price": pick["price"],
                "fpl_score": pick["fpl_score"],
                "form": pick["form"],
                "reasons": pick["recommendation_reasons"][:3],
                "llm_summary": player.get("llm_summary") if player else None,
            }
        )

    # Injury alerts (risk >= 5)
    injury_alerts = [
        {
            "player_id": p["player_id"],
            "web_name": p["web_name"],
            "team_short": p["team_short"],
            "position": p["position"],
            "injury_risk": p["injury_risk"],
            "injury_reasoning": p.get("injury_reasoning"),
        }
        for p in dashboard_rows
        if p.get("injury_risk") is not None and p["injury_risk"] >= 5
    ]
    injury_alerts.sort(key=lambda x: -x["injury_risk"])

    # Best and worst fixture runs
    team_fdr_list = []
    for team_id, fdr_data in fixture_fdr.items():
        team_info = team_map.get(team_id, {"name": f"Team {team_id}", "short_name": "???"})
        team_fdr_list.append(
            {
                "team_id": team_id,
                "team_name": team_info["name"],
                "team_short": team_info["short_name"],
                "fdr_next_3": round(fdr_data.get("next_3", 3.0), 1),
                "fdr_next_6": round(fdr_data.get("next_6", 3.0), 1),
            }
        )
    team_fdr_list.sort(key=lambda x: x["fdr_next_6"])
    best_fixtures = team_fdr_list[:3]
    worst_fixtures = team_fdr_list[-3:]

    # Form watch: rising and falling players
    rising = [
        {
            "player_id": p["player_id"],
            "web_name": p["web_name"],
            "team_short": p["team_short"],
            "position": p["position"],
            "form": p["form"],
            "fpl_score": p["fpl_score"],
        }
        for p in dashboard_rows
        if p.get("form_trend") == "improving"
    ]
    rising.sort(key=lambda x: -x["fpl_score"])

    falling = [
        {
            "player_id": p["player_id"],
            "web_name": p["web_name"],
            "team_short": p["team_short"],
            "position": p["position"],
            "form": p["form"],
            "fpl_score": p["fpl_score"],
        }
        for p in dashboard_rows
        if p.get("form_trend") == "declining"
    ]
    falling.sort(key=lambda x: x["fpl_score"])

    # Key themes from sentiment across top players
    all_themes: list[str] = []
    for p in dashboard_rows[:50]:  # Top 50 by rank
        themes = p.get("key_themes")
        if themes:
            all_themes.extend(themes)
    # Count and take top themes
    theme_counts: dict[str, int] = {}
    for theme in all_themes:
        theme_counts[theme] = theme_counts.get(theme, 0) + 1
    top_themes = sorted(theme_counts.items(), key=lambda x: -x[1])[:5]

    # Sell alerts
    sells = [t for t in transfer_rows if t["recommendation"] == "sell"]
    sells.sort(key=lambda x: x["fpl_score"])
    sell_alerts = [
        {
            "player_id": s["player_id"],
            "web_name": s["web_name"],
            "team_short": s["team_short"],
            "position": s["position"],
            "fpl_score": s["fpl_score"],
            "reasons": s["recommendation_reasons"][:2],
        }
        for s in sells[:3]
    ]

    briefing = {
        "season": season,
        "gameweek": gameweek,
        "advice_gameweek": advice_gameweek,
        "top_picks": top_picks,
        "sell_alerts": sell_alerts,
        "injury_alerts": injury_alerts[:5],
        "best_fixtures": best_fixtures,
        "worst_fixtures": worst_fixtures,
        "rising_players": rising[:5],
        "falling_players": falling[:5],
        "trending_themes": [{"theme": t, "count": c} for t, c in top_themes],
        "summary_stats": {
            "total_players": len(dashboard_rows),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "injury_count": len(injury_alerts),
            "improving_count": len(rising),
            "declining_count": len(falling),
        },
    }

    logger.info(
        "Built gameweek briefing: GW%d, %d picks, %d injuries, %d rising, %d falling",
        gameweek,
        len(top_picks),
        len(injury_alerts),
        len(rising),
        len(falling),
    )

    return briefing
