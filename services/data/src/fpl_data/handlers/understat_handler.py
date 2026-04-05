"""Lambda handler for Understat xG data collection."""

import logging
from typing import Any

from fpl_data.collectors.understat_collector import UnderstatCollector
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "fpl-data-lake-dev"


async def main(
    season: str,
    gameweek: int,
    output_bucket: str = DEFAULT_BUCKET,
    force: bool = False,
) -> dict[str, Any]:
    """Collect Understat league-level xG stats for the season.

    Args:
        season: Season identifier, e.g. "2025-26".
        gameweek: Gameweek number (passed by pipeline, unused by Understat).
        output_bucket: S3 bucket for output.
        force: If True, overwrite existing data.

    Returns:
        Dict with CollectionResponse result.
    """
    s3_client = S3Client()
    collector = UnderstatCollector(s3_client=s3_client, output_bucket=output_bucket)
    result = await collector.collect_league_stats(season, force=force)
    return result.model_dump()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for Understat collection."""
    return RunHandler(
        main_func=main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "force"],
    ).lambda_executor(lambda_event=event)
