"""Team strength curator — aggregates player data per team."""

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


def build_team_strength(
    dashboard_rows: list[dict[str, Any]],
    fixture_fdr: dict[int, dict[str, float]],
    team_map: dict[int, dict[str, str]],
    season: str,
    gameweek: int,
) -> list[dict[str, Any]]:
    """Build team strength aggregation from player dashboard data.

    Args:
        dashboard_rows: Output from build_player_dashboard.
        fixture_fdr: Team ID -> {"next_3", "next_6"} FDR averages.
        team_map: Team ID -> {"name", "short_name"} mapping.
        season: Season identifier.
        gameweek: Current gameweek number.

    Returns:
        List of 20 team strength dicts.
    """
    # Group players by team_name -> find team_id from team_map (reverse lookup)
    name_to_id = {v["name"]: k for k, v in team_map.items()}

    teams: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in dashboard_rows:
        teams[player["team_name"]].append(player)

    rows: list[dict[str, Any]] = []
    for team_name, players in sorted(teams.items()):
        team_id = name_to_id.get(team_name, 0)
        team_short = team_map.get(team_id, {}).get("short_name", "???")

        scores = [p["fpl_score"] for p in players]
        forms = [p["form"] for p in players]
        prices = [p["price"] for p in players]
        points = [p["total_points"] for p in players]

        top_scorer = max(players, key=lambda p: p["total_points"])
        enriched_count = sum(1 for p in players if p.get("llm_summary") is not None)

        fdr_data = fixture_fdr.get(team_id, {})

        rows.append(
            {
                "team_id": team_id,
                "team_name": team_name,
                "team_short": team_short,
                "avg_fpl_score": round(sum(scores) / len(scores), 1),
                "total_points": sum(points),
                "avg_form": round(sum(forms) / len(forms), 1),
                "squad_value": round(sum(prices), 1),
                "top_scorer_id": top_scorer["player_id"],
                "top_scorer_name": top_scorer["web_name"],
                "top_scorer_points": top_scorer["total_points"],
                "avg_fdr_remaining": round(fdr_data["next_6"], 1) if "next_6" in fdr_data else None,
                "player_count": len(players),
                "enriched_player_count": enriched_count,
                "season": season,
                "gameweek": gameweek,
            }
        )

    logger.info("Built team strength: %d teams", len(rows))
    return rows
