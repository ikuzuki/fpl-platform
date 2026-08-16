"""Lambda handler for fetching a user's FPL squad.

Invoked by the agent service via boto3 lambda_client.invoke() to retrieve
a user's raw squad picks. The agent enriches player IDs with names from
its own Neon database.
"""

import logging
from typing import Any

from fpl_data.collectors.team_fetcher import TeamFetcher
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)


async def main(
    team_id: int,
    gameweek: int,
) -> dict[str, Any]:
    """Fetch a user's FPL squad picks.

    Args:
        team_id: The FPL manager team ID.
        gameweek: The gameweek number.

    Returns:
        Raw squad dict with picks, active_chip, automatic_subs, entry_history.
    """
    fetcher = TeamFetcher()
    result = await fetcher.fetch_squad(team_id, gameweek)
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
    ).lambda_executor(lambda_event=event)
