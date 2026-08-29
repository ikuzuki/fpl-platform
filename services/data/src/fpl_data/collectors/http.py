"""Shared HTTP fetch for the FPL API, with an S3 mirror fallback.

All FPL API collectors should use `fpl_fetch` instead of implementing their
own retry logic.

Cloudflare rejects most AWS Lambda egress addresses outright: roughly a
quarter of cold sandboxes get a 200 and the rest get a 403 on every request
for the life of that sandbox. Retrying inside an invocation cannot recover —
the address does not change — so a scheduled job on a GitHub Actions runner
mirrors each endpoint to S3 (see `scripts/mirror_fpl_api.py`) and a blocked
Lambda reads the mirrored snapshot instead.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta

from curl_cffi.requests import AsyncSession

from fpl_lib.clients.s3 import S3Client

logger = logging.getLogger(__name__)

FPL_BASE_URL = "https://fantasy.premierleague.com/api"

MIRROR_PREFIX = "raw/fpl-api-mirror"
DEFAULT_BUCKET = "fpl-data-lake-dev"

# A blocked sandbox 403s every attempt, so the ladder only buys a slower
# failure. Keep just enough attempts to ride out a genuine transient error.
MAX_BACKOFF_SECONDS = 4

# The mirror job runs daily. Two days of slack covers one missed run; beyond
# that the snapshot is too stale to build a gameweek from and the caller
# should fail rather than publish last week's prices as current.
MAX_MIRROR_AGE = timedelta(days=2)


def mirror_prefix_for(url: str) -> str:
    """S3 prefix holding mirrored snapshots of an FPL API endpoint."""
    endpoint = url.split("/api/", 1)[-1].strip("/")
    return f"{MIRROR_PREFIX}/{endpoint}/"


def read_mirror(url: str, bucket: str | None = None) -> dict | list:
    """Read the most recent mirrored snapshot of an endpoint.

    Args:
        url: The FPL API URL the mirror stands in for.
        bucket: Data lake bucket. Defaults to $DATA_LAKE_BUCKET.

    Returns:
        Parsed JSON from the newest snapshot.

    Raises:
        FileNotFoundError: If no snapshot exists for the endpoint.
        RuntimeError: If the newest snapshot is older than MAX_MIRROR_AGE.
    """
    bucket = bucket or os.environ.get("DATA_LAKE_BUCKET", DEFAULT_BUCKET)
    prefix = mirror_prefix_for(url)

    keys = S3Client().list_objects(bucket, prefix)
    if not keys:
        raise FileNotFoundError(f"No mirrored snapshot at s3://{bucket}/{prefix}")

    # Keys are ISO-8601 timestamps, so lexical order is chronological order.
    latest = max(keys)
    age = datetime.now(UTC) - _snapshot_taken_at(latest)
    if age > MAX_MIRROR_AGE:
        raise RuntimeError(
            f"Mirrored snapshot s3://{bucket}/{latest} is {age} old "
            f"(limit {MAX_MIRROR_AGE}) — refusing to serve it as current data"
        )

    logger.warning(
        "[FPL API] serving mirrored snapshot s3://%s/%s (age %s) — live fetch was blocked",
        bucket,
        latest,
        age,
    )
    return S3Client().read_json(bucket, latest)


def _snapshot_taken_at(key: str) -> datetime:
    """Parse the ISO-8601 timestamp a mirror key ends with."""
    stamp = key.rsplit("/", 1)[-1].removesuffix(".json")
    return datetime.fromisoformat(stamp)


async def fpl_fetch(url: str, max_retries: int = 3, *, allow_mirror: bool = True) -> dict | list:
    """Fetch JSON from the FPL API, falling back to the S3 mirror on 403.

    Args:
        url: Full URL to fetch.
        max_retries: Maximum live attempts before falling back (default 3).
        allow_mirror: If False, raise rather than reading the mirror. The
            mirror job itself sets this — mirroring its own output would
            freeze the snapshot at whatever it last managed to fetch.

    Returns:
        Parsed JSON response (dict or list).

    Raises:
        curl_cffi.requests.errors.HTTPError: On a non-403 HTTP error, or on a
            403 when the mirror is unavailable or too stale.
    """
    last_response = None

    for attempt in range(max_retries):
        # A fresh session per attempt, so a retry is a new connection rather
        # than another request down the one Cloudflare already rejected.
        async with AsyncSession(impersonate="chrome", timeout=30) as session:
            logger.info("[FPL API] GET %s (attempt %d/%d)", url, attempt + 1, max_retries)
            response = await session.get(url)
            logger.info(
                "[FPL API] %s | status=%d | size=%d bytes",
                url.split("/api/")[-1] if "/api/" in url else url,
                response.status_code,
                len(response.content),
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code != 403:
                response.raise_for_status()

            last_response = response

        if attempt < max_retries - 1:
            wait = min(2 ** (attempt + 1), MAX_BACKOFF_SECONDS)
            logger.warning(
                "[FPL API] 403 Forbidden — retrying in %ds (attempt %d/%d)",
                wait,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(wait)

    if allow_mirror:
        logger.warning("[FPL API] %s blocked after %d attempts — falling back", url, max_retries)
        return read_mirror(url)

    assert last_response is not None
    last_response.raise_for_status()
    raise AssertionError("unreachable: raise_for_status() on a 403 always raises")
