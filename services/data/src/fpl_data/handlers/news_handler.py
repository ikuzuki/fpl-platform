"""Lambda handler for news/RSS data collection."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fpl_data.collectors.news_collector import NewsCollector
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "fpl-data-lake-dev"
COLLECTION_WINDOW_DAYS = 7


async def main(
    season: str,
    gameweek: int,
    output_bucket: str = DEFAULT_BUCKET,
    force: bool = False,
) -> dict[str, Any]:
    """Collect football news from RSS feeds for the last 7 days.

    RSS feeds only contain recent articles, so we collect for each day
    in the window. Already-collected days are skipped (idempotent)
    unless force=True.

    Args:
        season: Season identifier (passed by pipeline, used for context).
        gameweek: Gameweek number (passed by pipeline, unused by news collector).
        output_bucket: S3 bucket for output.
        force: If True, overwrite existing data.

    Returns:
        Dict with total records collected across all days.
    """
    s3_client = S3Client()
    collector = NewsCollector(s3_client=s3_client, output_bucket=output_bucket)
    today = datetime.now(UTC)

    total_collected = 0
    days_collected = 0

    for days_ago in range(COLLECTION_WINDOW_DAYS):
        date_str = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        result = await collector.collect_rss_feeds(date_str, force=force)
        total_collected += result.records_collected
        if result.records_collected > 0:
            days_collected += 1

    logger.info(
        "News collection complete: %d articles across %d days (window=%d)",
        total_collected,
        days_collected,
        COLLECTION_WINDOW_DAYS,
    )

    return {
        "status": "success",
        "records_collected": total_collected,
        "days_collected": days_collected,
        "output_path": "raw/news/",
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for news collection."""
    return RunHandler(
        main_func=main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "force"],
    ).lambda_executor(lambda_event=event)
