"""Mirror the FPL API to S3 from a runner that Cloudflare does not block.

Cloudflare rejects most AWS Lambda egress addresses, so the collectors cannot
rely on reaching fantasy.premierleague.com. This job runs on a GitHub Actions
runner — which reaches the API cleanly — and writes a snapshot of each
endpoint the pipeline needs to `raw/fpl-api-mirror/`, where `fpl_fetch` picks
it up when its own request is blocked.

Usage:
    python scripts/mirror_fpl_api.py
    python scripts/mirror_fpl_api.py --season 2026-27 --bucket fpl-data-lake-dev
"""

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime

from fpl_data.collectors.http import FPL_BASE_URL, fpl_fetch, mirror_prefix_for
from fpl_lib.clients.s3 import S3Client
from fpl_lib.utils.date_utils import current_season

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "fpl-data-lake-dev"


async def mirror_endpoint(s3_client: S3Client, bucket: str, url: str) -> dict | list:
    """Fetch one endpoint, write it to its mirror prefix, and return the snapshot."""
    data = await fpl_fetch(url, allow_mirror=False)
    key = f"{mirror_prefix_for(url)}{datetime.now(UTC).isoformat()}.json"
    s3_client.put_json(bucket, key, data)

    records = len(data) if isinstance(data, list) else len(data.get("elements", []))
    logger.info("Mirrored %s -> s3://%s/%s (%d records)", url, bucket, key, records)
    return data


def latest_finished_gameweek(bootstrap: dict) -> int:
    """Highest gameweek marked finished in bootstrap, or 0 before the season starts."""
    return max((e["id"] for e in bootstrap.get("events", []) if e.get("finished")), default=0)


async def main(season: str, bucket: str) -> None:
    """Mirror bootstrap, fixtures, and the latest finished gameweek's live data."""
    s3_client = S3Client()

    bootstrap = await mirror_endpoint(s3_client, bucket, f"{FPL_BASE_URL}/bootstrap-static/")
    await mirror_endpoint(s3_client, bucket, f"{FPL_BASE_URL}/fixtures/")

    gameweek = latest_finished_gameweek(bootstrap)
    if gameweek == 0:
        logger.info("No finished gameweeks yet for %s — nothing more to mirror", season)
        return

    await mirror_endpoint(s3_client, bucket, f"{FPL_BASE_URL}/event/{gameweek}/live/")
    logger.info("Mirror complete for season=%s through GW%d", season, gameweek)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mirror the FPL API to S3")
    parser.add_argument("--season", default=None, help="Season identifier, e.g. 2026-27")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Data lake bucket")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(season=args.season or current_season(), bucket=args.bucket))
    except Exception:
        logger.exception("FPL API mirror failed")
        sys.exit(1)
