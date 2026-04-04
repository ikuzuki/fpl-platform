"""Collector for Understat xG statistics.

Understat provides advanced stats (xG, xA, shots, key passes) via an internal
POST API. We collect season-level player stats for the EPL.

Endpoint: POST https://understat.com/main/getPlayersStats/
Params: league (e.g. "EPL"), season (e.g. "2024" for 2024-25)
"""

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import CollectionResponse

logger = logging.getLogger(__name__)

UNDERSTAT_BASE_URL = "https://understat.com/main"


def _season_to_understat_year(season: str) -> str:
    """Convert FPL season format '2025-26' to Understat year '2025'."""
    return season.split("-")[0]


class UnderstatCollector:
    """Collects xG statistics from Understat and writes raw JSON to S3."""

    def __init__(self, s3_client: S3Client, output_bucket: str) -> None:
        self.s3_client = s3_client
        self.output_bucket = output_bucket

    async def collect_league_stats(
        self, season: str, league: str = "EPL", *, force: bool = False
    ) -> CollectionResponse:
        """Collect season-level player stats for an entire league.

        Args:
            season: FPL season identifier, e.g. "2025-26".
            league: Understat league code. Defaults to "EPL".
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = number of players.
        """
        prefix = f"raw/understat/season={season}/league_stats/"
        if not force and self._output_exists(prefix):
            logger.info("Understat league stats already exist for season=%s, skipping", season)
            return CollectionResponse(status="success", records_collected=0, output_path=prefix)

        understat_year = _season_to_understat_year(season)
        data = await self._fetch_player_stats(league, understat_year)

        timestamp = datetime.now(UTC).isoformat()
        key = f"{prefix}{timestamp}.json"
        self.s3_client.put_json(self.output_bucket, key, data)

        records = len(data)
        logger.info(
            "Collected Understat league stats: %d players for season=%s",
            records,
            season,
        )
        return CollectionResponse(status="success", records_collected=records, output_path=key)

    async def collect_player_stats(
        self,
        understat_player_id: int,
        season: str,
        league: str = "EPL",
        *,
        force: bool = False,
    ) -> CollectionResponse:
        """Collect stats for a single player from the league dataset.

        Fetches the full league stats and filters to the requested player.
        Rate-limited: sleeps 1.5s before fetching to be respectful.

        Args:
            understat_player_id: Understat player ID.
            season: FPL season identifier, e.g. "2025-26".
            league: Understat league code. Defaults to "EPL".
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = 1 if found, 0 if not.
        """
        prefix = f"raw/understat/season={season}/players/{understat_player_id}/"
        if not force and self._output_exists(prefix):
            logger.info(
                "Understat player stats already exist for player=%d season=%s, skipping",
                understat_player_id,
                season,
            )
            return CollectionResponse(status="success", records_collected=0, output_path=prefix)

        await asyncio.sleep(1.5)  # Rate limit — Understat is a community resource

        understat_year = _season_to_understat_year(season)
        all_players = await self._fetch_player_stats(league, understat_year)

        player_data = [p for p in all_players if str(p.get("id")) == str(understat_player_id)]

        if not player_data:
            logger.warning(
                "Player %d not found in Understat %s %s data",
                understat_player_id,
                league,
                season,
            )
            return CollectionResponse(status="partial", records_collected=0, output_path=prefix)

        timestamp = datetime.now(UTC).isoformat()
        key = f"{prefix}{timestamp}.json"
        self.s3_client.put_json(self.output_bucket, key, player_data[0])

        logger.info(
            "Collected Understat stats for player=%d (%s) season=%s",
            understat_player_id,
            player_data[0].get("player_name", "unknown"),
            season,
        )
        return CollectionResponse(status="success", records_collected=1, output_path=key)

    async def _fetch_player_stats(self, league: str, year: str) -> list[dict]:
        """Fetch all player stats for a league/season from Understat.

        Args:
            league: Understat league code (e.g. "EPL").
            year: Start year of the season (e.g. "2024" for 2024-25).

        Returns:
            List of player stat dicts with keys: id, player_name, games,
            time, goals, xG, assists, xA, shots, key_passes, position, etc.
        """
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30.0,
        ) as client:
            response = await client.post(
                f"{UNDERSTAT_BASE_URL}/getPlayersStats/",
                data={"league": league, "season": year},
            )
            response.raise_for_status()
            data = response.json()

        if not data.get("success"):
            msg = f"Understat API returned success=false for {league}/{year}"
            raise ValueError(msg)

        return data["players"]

    def _output_exists(self, prefix: str) -> bool:
        """Check if any objects exist under the given S3 prefix."""
        existing = self.s3_client.list_objects(self.output_bucket, prefix)
        return len(existing) > 0
