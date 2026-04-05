"""Lambda handler to resolve the latest finished gameweek from the FPL API.

Used as the first step in the Step Functions pipeline. Returns season and
gameweek for downstream steps, or signals skip if no new gameweek is available.
"""

import logging
from typing import Any

from fpl_data.collectors.gameweek_resolver import resolve_gameweek
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)


async def main(
    season: str = "2025-26",
    last_processed_gw: int = 0,
    force: bool = False,
) -> dict[str, Any]:
    """Resolve the latest finished gameweek and decide whether to run the pipeline.

    Args:
        season: Season identifier.
        last_processed_gw: The last gameweek that was successfully processed.
            If 0, process the latest finished gameweek.
        force: If True, always return a gameweek to process (ignore last_processed_gw).

    Returns:
        Dict with season, gameweek, force, and should_run flag.
    """
    info = await resolve_gameweek(season=season)

    target_gw = info.latest_finished_gw

    if target_gw == 0:
        logger.info("No finished gameweeks yet for season %s", season)
        return {
            "season": season,
            "gameweek": 0,
            "force": force,
            "should_run": False,
            "reason": "No finished gameweeks",
        }

    if not force and target_gw <= last_processed_gw:
        logger.info(
            "GW%d already processed (latest_finished=%d), skipping",
            last_processed_gw,
            target_gw,
        )
        return {
            "season": season,
            "gameweek": target_gw,
            "force": force,
            "should_run": False,
            "reason": f"GW{target_gw} already processed",
        }

    logger.info("Pipeline should run for %s GW%d", season, target_gw)
    return {
        "season": season,
        "gameweek": target_gw,
        "force": force,
        "should_run": True,
        "reason": f"New gameweek available: GW{target_gw}",
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for gameweek resolution."""
    return RunHandler(
        main_func=main,
        required_main_params=[],
        optional_main_params=["season", "last_processed_gw", "force"],
    ).lambda_executor(lambda_event=event)
