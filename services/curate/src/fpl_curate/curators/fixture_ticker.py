"""Fixture ticker curator — builds the FDR heatmap dataset and fixture lookup."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_fixture_ticker(
    fixtures_raw: list[dict[str, Any]],
    team_map: dict[int, dict[str, str]],
    current_gw: int,
    season: str,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, float]]]:
    """Build fixture ticker rows and per-team FDR averages.

    Args:
        fixtures_raw: Raw fixtures JSON from FPL API.
        team_map: Mapping of team_id -> {"name": ..., "short_name": ...}.
        current_gw: Current gameweek (fixtures after this are included).
        season: Season identifier.

    Returns:
        Tuple of (fixture_ticker_rows, fixture_fdr_lookup).
        fixture_fdr_lookup maps team_id -> {"next_3": avg_fdr, "next_6": avg_fdr}.
    """
    # Filter to remaining fixtures
    remaining = [f for f in fixtures_raw if f.get("event") is not None and f["event"] > current_gw]
    remaining.sort(key=lambda f: (f["event"], f.get("kickoff_time", "")))

    rows: list[dict[str, Any]] = []
    # Track per-team FDR values for averaging
    team_fdrs: dict[int, list[int]] = {}

    for fixture in remaining:
        gw = fixture["event"]
        home_id = fixture["team_h"]
        away_id = fixture["team_a"]
        home_fdr = fixture.get("team_h_difficulty", 3)
        away_fdr = fixture.get("team_a_difficulty", 3)
        kickoff = fixture.get("kickoff_time")

        home_team = team_map.get(home_id, {"name": f"Team {home_id}", "short_name": "???"})
        away_team = team_map.get(away_id, {"name": f"Team {away_id}", "short_name": "???"})

        # Home team row
        rows.append(
            {
                "team_id": home_id,
                "team_name": home_team["name"],
                "team_short": home_team["short_name"],
                "gameweek": gw,
                "opponent": away_team["name"],
                "opponent_short": away_team["short_name"],
                "is_home": True,
                "fdr": home_fdr,
                "kickoff_time": kickoff,
                "season": season,
            }
        )

        # Away team row
        rows.append(
            {
                "team_id": away_id,
                "team_name": away_team["name"],
                "team_short": away_team["short_name"],
                "gameweek": gw,
                "opponent": home_team["name"],
                "opponent_short": home_team["short_name"],
                "is_home": False,
                "fdr": away_fdr,
                "kickoff_time": kickoff,
                "season": season,
            }
        )

        # Accumulate FDR for averages
        team_fdrs.setdefault(home_id, []).append(home_fdr)
        team_fdrs.setdefault(away_id, []).append(away_fdr)

    # Build FDR lookup: next_3 and next_6 averages
    fixture_fdr: dict[int, dict[str, float]] = {}
    for team_id, fdrs in team_fdrs.items():
        fixture_fdr[team_id] = {
            "next_3": sum(fdrs[:3]) / min(len(fdrs), 3) if fdrs else 3.0,
            "next_6": sum(fdrs[:6]) / min(len(fdrs), 6) if fdrs else 3.0,
        }

    logger.info(
        "Built fixture ticker: %d rows for %d teams, GW %d-%d",
        len(rows),
        len(team_fdrs),
        current_gw + 1,
        max((f["event"] for f in remaining), default=current_gw),
    )

    return rows, fixture_fdr


def build_team_map(bootstrap_data: dict[str, Any]) -> dict[int, dict[str, str]]:
    """Extract team ID -> name/short_name mapping from bootstrap JSON.

    Args:
        bootstrap_data: Raw FPL API bootstrap-static response.

    Returns:
        Dict mapping team_id to {"name": ..., "short_name": ...}.
    """
    return {
        t["id"]: {"name": t["name"], "short_name": t["short_name"]}
        for t in bootstrap_data.get("teams", [])
    }
