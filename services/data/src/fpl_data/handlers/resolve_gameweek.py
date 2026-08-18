"""Lambda handler to resolve the latest finished gameweek from the FPL API.

Used as the first step in the Step Functions pipeline. Returns season and
gameweek for downstream steps, or signals skip if no new gameweek is available.
"""

import logging
import re
from typing import Any

from fpl_data.collectors.gameweek_resolver import resolve_gameweek
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler
from fpl_lib.utils.date_utils import current_season

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "fpl-data-lake-dev"

# A gameweek counts as processed once curate has written its player_dashboard
# parquet — the last artefact a run produces. An earlier marker such as the
# clean parquet also survives a run that died during enrichment, which would
# strand that gameweek as permanently "done" without ever completing it.
PROCESSED_MARKER_PREFIX = "curated/player_dashboard"

_GAMEWEEK_IN_KEY = re.compile(r"/gameweek=(\d+)/")


def latest_processed_gameweek(s3_client: S3Client, bucket: str, season: str) -> int:
    """Highest gameweek this season with a completed run, or 0 if there are none."""
    keys = s3_client.list_objects(bucket, f"{PROCESSED_MARKER_PREFIX}/season={season}/")
    gameweeks = [int(match.group(1)) for key in keys if (match := _GAMEWEEK_IN_KEY.search(key))]
    return max(gameweeks, default=0)


async def main(
    season: str | None = None,
    last_processed_gw: int | None = None,
    force: bool = False,
    output_bucket: str = DEFAULT_BUCKET,
) -> dict[str, Any]:
    """Resolve the latest finished gameweek and decide whether to run the pipeline.

    Args:
        season: Season identifier. Defaults to the season the current date falls in,
            which is what the scheduled pipeline relies on. Pass explicitly to backfill.
        last_processed_gw: The last gameweek that was successfully processed. Derived
            from the completed runs already in S3 when omitted, so the daily schedule
            is a no-op until a new gameweek finishes. Pass explicitly to override.
        force: If True, always return a gameweek to process (ignore last_processed_gw).
        output_bucket: Bucket holding the processed-run markers.

    Returns:
        Dict with season, gameweek, force, and should_run flag.
    """
    season = season or current_season()

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

    if last_processed_gw is None:
        last_processed_gw = latest_processed_gameweek(S3Client(), output_bucket, season)
        logger.info(
            "Derived last_processed_gw=%d for %s from completed runs in s3://%s/%s",
            last_processed_gw,
            season,
            output_bucket,
            PROCESSED_MARKER_PREFIX,
        )

    if not force and target_gw <= last_processed_gw:
        logger.info(
            "GW%d already processed (last_processed=%d), skipping",
            target_gw,
            last_processed_gw,
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
        optional_main_params=["season", "last_processed_gw", "force", "output_bucket"],
    ).lambda_executor(lambda_event=event)
