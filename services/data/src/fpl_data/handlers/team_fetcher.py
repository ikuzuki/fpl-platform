"""Lambda handler for fetching a user's FPL squad.

Invoked by the agent service via boto3 lambda_client.invoke() to retrieve
a user's squad picks enriched with player names and positions.
"""

import logging
from typing import Any

from fpl_data.collectors.team_fetcher import TeamFetcher
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)


async def main(
    team_id: int,
    gameweek: int,
    season: str = "2025-26",
) -> dict[str, Any]:
    """Fetch and enrich a user's FPL squad.

    Args:
        team_id: The FPL manager team ID.
        gameweek: The gameweek number.
        season: Season string (currently unused, reserved for future).

    Returns:
        Enriched squad dict with player names, positions, captain info.
    """
    fetcher = TeamFetcher()

    # Fetch bootstrap data for player name enrichment.
    bootstrap_url = f"{TeamFetcher.FPL_BASE_URL}/bootstrap-static/"
    bootstrap_data = await fetcher._fetch(bootstrap_url)

    result = await fetcher.fetch_squad_with_names(team_id, gameweek, bootstrap_data)
    logger.info(
        "Fetched squad for team %d GW%d: %d picks",
        team_id,
        gameweek,
        len(result.get("picks", [])),
    )
    return result


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for team fetching."""
    return RunHandler(
        main_func=main,
        required_main_params=["team_id", "gameweek"],
        optional_main_params=["season"],
    ).lambda_executor(lambda_event=event)
