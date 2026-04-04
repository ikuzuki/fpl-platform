"""Lambda handler for FPL API data collection."""

import logging
from typing import Any

from fpl_data.collectors.fpl_api_collector import FPLAPICollector
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

REQUIRED_PARAMS = ["season", "gameweek"]
OPTIONAL_PARAMS = ["output_bucket", "endpoints", "force"]

DEFAULT_BUCKET = "fpl-data-lake-dev"
DEFAULT_ENDPOINTS = ["bootstrap", "fixtures", "live"]


async def main(
    season: str,
    gameweek: int,
    output_bucket: str = DEFAULT_BUCKET,
    endpoints: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Collect FPL API data for the given season and gameweek.

    Args:
        season: Season identifier, e.g. "2025-26".
        gameweek: Gameweek number (1-38).
        output_bucket: S3 bucket for output.
        endpoints: List of endpoints to collect. Defaults to bootstrap + fixtures + live.
        force: If True, overwrite existing data.

    Returns:
        Dict with list of CollectionResponse results.
    """
    s3_client = S3Client()
    collector = FPLAPICollector(s3_client=s3_client, output_bucket=output_bucket)

    active_endpoints = endpoints or DEFAULT_ENDPOINTS
    results = []

    for endpoint in active_endpoints:
        if endpoint == "bootstrap":
            resp = await collector.collect_bootstrap(season, force=force)
        elif endpoint == "fixtures":
            resp = await collector.collect_fixtures(season, force=force)
        elif endpoint == "live":
            resp = await collector.collect_gameweek_live(season, gameweek, force=force)
        else:
            logger.warning("Unknown endpoint: %s, skipping", endpoint)
            continue
        results.append(resp.model_dump())

    return {"responses": results}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for FPL API collection."""
    return RunHandler(
        main_func=main,
        required_main_params=REQUIRED_PARAMS,
        optional_main_params=OPTIONAL_PARAMS,
    ).lambda_executor(lambda_event=event)
