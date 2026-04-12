"""Fetch a user's FPL squad by team ID.

Uses curl_cffi with Chrome TLS impersonation to bypass Cloudflare.
Endpoint: https://fantasy.premierleague.com/api/entry/{team_id}/event/{gameweek}/picks/
"""

import asyncio
import logging
import time
from typing import Any

from curl_cffi.requests import AsyncSession

from fpl_data.collectors.exceptions import FPLAccessError, TeamNotFoundError

logger = logging.getLogger(__name__)

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


class TeamFetcher:
    """Fetches FPL manager squad data with Chrome TLS impersonation."""

    FPL_BASE_URL = "https://fantasy.premierleague.com/api"
    MAX_REQUESTS_PER_MINUTE = 5

    def __init__(self) -> None:
        self._request_times: list[float] = []

    async def fetch_squad(self, team_id: int, gameweek: int) -> dict[str, Any]:
        """Fetch a user's FPL squad picks for a given gameweek.

        Args:
            team_id: The FPL manager team ID.
            gameweek: The gameweek number.

        Returns:
            Dict with picks, active_chip, automatic_subs, and entry_history.

        Raises:
            TeamNotFoundError: If the team ID does not exist (404).
            FPLAccessError: If the FPL API returns 403 after retry.
        """
        url = f"{self.FPL_BASE_URL}/entry/{team_id}/event/{gameweek}/picks/"
        return await self._fetch(url, team_id=team_id)

    async def fetch_squad_with_names(
        self,
        team_id: int,
        gameweek: int,
        bootstrap_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch squad and enrich picks with player names and positions.

        Args:
            team_id: The FPL manager team ID.
            gameweek: The gameweek number.
            bootstrap_data: FPL bootstrap-static data containing elements and teams.

        Returns:
            Enriched squad dict with player names, positions, captain, and vice_captain.
        """
        squad = await self.fetch_squad(team_id, gameweek)

        player_lookup = {el["id"]: el for el in bootstrap_data.get("elements", [])}
        team_lookup = {t["id"]: t["name"] for t in bootstrap_data.get("teams", [])}

        captain = None
        vice_captain = None

        for pick in squad.get("picks", []):
            element_id = pick.get("element")
            player = player_lookup.get(element_id, {})
            pick["web_name"] = player.get("web_name", "Unknown")
            pick["position"] = POSITION_MAP.get(player.get("element_type", 0), "N/A")
            pick["team_name"] = team_lookup.get(player.get("team", 0), "Unknown")

            if pick.get("is_captain"):
                captain = pick["web_name"]
            if pick.get("is_vice_captain"):
                vice_captain = pick["web_name"]

        squad["captain"] = captain
        squad["vice_captain"] = vice_captain

        return squad

    async def _fetch(self, url: str, team_id: int = 0) -> dict[str, Any]:
        """Fetch JSON from the FPL API with 403 retry.

        Args:
            url: The FPL API URL to fetch.
            team_id: The team ID (for error messages).

        Returns:
            Parsed JSON response dict.

        Raises:
            TeamNotFoundError: On 404.
            FPLAccessError: On 403 after one retry.
        """
        await self._enforce_rate_limit()

        async with AsyncSession(impersonate="chrome", timeout=30) as session:
            logger.info("[FPL API] GET %s", url)
            response = await session.get(url)

            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result

            if response.status_code == 404:
                raise TeamNotFoundError(team_id)

            if response.status_code == 403:
                logger.warning("[FPL API] 403 Forbidden — retrying in 2s")
                await asyncio.sleep(2)
                await self._enforce_rate_limit()
                response = await session.get(url)

                if response.status_code == 200:
                    result = response.json()
                    return result

                raise FPLAccessError(team_id, f"status={response.status_code}")

            response.raise_for_status()

        # Unreachable but satisfies type checker.
        return response.json()  # type: ignore[return-value]

    async def _enforce_rate_limit(self) -> None:
        """Enforce max requests per minute by sleeping if needed."""
        now = time.time()
        # Remove timestamps older than 60 seconds.
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= self.MAX_REQUESTS_PER_MINUTE:
            oldest = self._request_times[0]
            wait = 60 - (now - oldest)
            if wait > 0:
                logger.info("[Rate Limit] Sleeping %.1fs", wait)
                await asyncio.sleep(wait)

        self._request_times.append(time.time())
