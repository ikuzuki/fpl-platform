"""Collector for the official FPL API.

FPL API is public, no auth required. Base URL: https://fantasy.premierleague.com/api

Uses curl_cffi to impersonate Chrome's TLS fingerprint, which prevents
Cloudflare from blocking requests originating from AWS Lambda IPs.
"""

import logging
from datetime import UTC, datetime

from fpl_data.collectors.http import FPL_BASE_URL, fpl_fetch
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import CollectionResponse

logger = logging.getLogger(__name__)


class FPLAPICollector:
    """Collects data from the official FPL API and writes raw JSON to S3."""

    def __init__(self, s3_client: S3Client, output_bucket: str) -> None:
        self.s3_client = s3_client
        self.output_bucket = output_bucket
        self._bootstrap_cache: dict | None = None

    async def collect_bootstrap(self, season: str, *, force: bool = False) -> CollectionResponse:
        """Collect bootstrap-static data (all players, teams, gameweeks).

        Args:
            season: Season identifier, e.g. "2025-26".
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = number of player elements.
        """
        prefix = f"raw/fpl-api/season={season}/bootstrap/"
        if not force and self._output_exists(prefix):
            logger.info("Bootstrap data already exists for season=%s, skipping", season)
            return CollectionResponse(status="success", records_collected=0, output_path=prefix)

        data = await self._fetch_bootstrap()
        timestamp = datetime.now(UTC).isoformat()
        key = f"{prefix}{timestamp}.json"
        self.s3_client.put_json(self.output_bucket, key, data)

        records = len(data.get("elements", []))
        logger.info("Collected bootstrap: %d players for season=%s", records, season)
        return CollectionResponse(status="success", records_collected=records, output_path=key)

    async def collect_fixtures(self, season: str, *, force: bool = False) -> CollectionResponse:
        """Collect all fixtures for the season.

        Args:
            season: Season identifier, e.g. "2025-26".
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = number of fixtures.
        """
        prefix = f"raw/fpl-api/season={season}/fixtures/"
        if not force and self._output_exists(prefix):
            logger.info("Fixtures data already exists for season=%s, skipping", season)
            return CollectionResponse(status="success", records_collected=0, output_path=prefix)

        data = await fpl_fetch(f"{FPL_BASE_URL}/fixtures/")
        timestamp = datetime.now(UTC).isoformat()
        key = f"{prefix}{timestamp}.json"
        self.s3_client.put_json(self.output_bucket, key, data)

        records = len(data) if isinstance(data, list) else 0
        logger.info("Collected fixtures: %d for season=%s", records, season)
        return CollectionResponse(status="success", records_collected=records, output_path=key)

    async def collect_gameweek_live(
        self, season: str, gameweek: int, *, force: bool = False
    ) -> CollectionResponse:
        """Collect live gameweek data.

        Args:
            season: Season identifier, e.g. "2025-26".
            gameweek: Gameweek number (1-38).
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = number of player entries.

        Raises:
            ValueError: If the gameweek has not finished yet.
        """
        # Guard: reject future/unfinished gameweeks
        await self._validate_gameweek_finished(gameweek)

        prefix = f"raw/fpl-api/season={season}/gameweek={gameweek:02d}/"
        if not force and self._output_exists(prefix):
            logger.info(
                "Gameweek live data already exists for season=%s gw=%d, skipping",
                season,
                gameweek,
            )
            return CollectionResponse(status="success", records_collected=0, output_path=prefix)

        data = await fpl_fetch(f"{FPL_BASE_URL}/event/{gameweek}/live/")
        timestamp = datetime.now(UTC).isoformat()
        key = f"{prefix}{timestamp}.json"
        self.s3_client.put_json(self.output_bucket, key, data)

        records = len(data.get("elements", []))
        logger.info(
            "Collected gameweek live: %d players for season=%s gw=%d",
            records,
            season,
            gameweek,
        )
        return CollectionResponse(status="success", records_collected=records, output_path=key)

    async def collect_player_history(
        self, player_id: int, season: str, *, force: bool = False
    ) -> CollectionResponse:
        """Collect detailed history for a single player.

        Args:
            player_id: FPL player element ID.
            season: Season identifier, e.g. "2025-26".
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = number of history entries.
        """
        prefix = f"raw/fpl-api/season={season}/players/{player_id}/"
        if not force and self._output_exists(prefix):
            logger.info(
                "Player history already exists for player=%d season=%s, skipping",
                player_id,
                season,
            )
            return CollectionResponse(status="success", records_collected=0, output_path=prefix)

        data = await fpl_fetch(f"{FPL_BASE_URL}/element-summary/{player_id}/")
        timestamp = datetime.now(UTC).isoformat()
        key = f"{prefix}{timestamp}.json"
        self.s3_client.put_json(self.output_bucket, key, data)

        records = len(data.get("history", []))
        logger.info(
            "Collected player history: %d entries for player=%d season=%s",
            records,
            player_id,
            season,
        )
        return CollectionResponse(status="success", records_collected=records, output_path=key)

    async def _fetch_bootstrap(self) -> dict:
        """Fetch bootstrap-static data, caching for reuse within the same invocation."""
        if self._bootstrap_cache is None:
            self._bootstrap_cache = await fpl_fetch(f"{FPL_BASE_URL}/bootstrap-static/")
        return self._bootstrap_cache

    async def _validate_gameweek_finished(self, gameweek: int) -> None:
        """Check that the requested gameweek has finished.

        Raises:
            ValueError: If the gameweek has not finished yet.
        """
        data = await self._fetch_bootstrap()
        events = data.get("events", [])

        for event in events:
            if event["id"] == gameweek:
                if not event.get("finished"):
                    raise ValueError(
                        f"Gameweek {gameweek} has not finished yet "
                        f"(is_current={event.get('is_current')}, "
                        f"finished={event.get('finished')})"
                    )
                return

        raise ValueError(f"Gameweek {gameweek} not found in FPL API events")

    def _output_exists(self, prefix: str) -> bool:
        """Check if any objects exist under the given S3 prefix."""
        existing = self.s3_client.list_objects(self.output_bucket, prefix)
        return len(existing) > 0
