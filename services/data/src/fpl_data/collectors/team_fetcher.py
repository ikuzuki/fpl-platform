"""Fetch a user's FPL squad by team ID.

Uses the shared fpl_fetch for Cloudflare bypass. Adds team-specific error
handling (404 → TeamNotFoundError, 403 → FPLAccessError) since user-facing
endpoints have different failure modes from public ones.
"""

import asyncio
import logging
import time
from typing import Any

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError

from fpl_data.collectors.exceptions import FPLAccessError, TeamNotFoundError
from fpl_data.collectors.http import FPL_BASE_URL

logger = logging.getLogger(__name__)


class TeamFetcher:
    """Fetches FPL manager squad data with Chrome TLS impersonation."""

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
            FPLAccessError: If the FPL API returns 403 after retries.
        """
        url = f"{FPL_BASE_URL}/entry/{team_id}/event/{gameweek}/picks/"
        return await self._fetch(url, team_id=team_id)

    async def _fetch(self, url: str, team_id: int = 0) -> dict[str, Any]:
        """Fetch JSON from the FPL API with team-specific error handling.

        Uses the same curl_cffi + Chrome impersonation as fpl_fetch, but maps
        404 → TeamNotFoundError and 403 → FPLAccessError after retry.

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
            logger.info("[FPL API] GET %s (attempt 1/2)", url)
            response = await session.get(url)
            logger.info(
                "[FPL API] %s | status=%d | size=%d bytes",
                url.split("/api/")[-1],
                response.status_code,
                len(response.content),
            )

            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result

            if response.status_code == 404:
                raise TeamNotFoundError(team_id)

            if response.status_code == 403:
                logger.warning("[FPL API] 403 Forbidden — retrying in 2s (attempt 2/2)")
                await asyncio.sleep(2)
                await self._enforce_rate_limit()
                response = await session.get(url)

                if response.status_code == 200:
                    result = response.json()
                    return result

                raise FPLAccessError(team_id, f"status={response.status_code}")

            raise RequestsError(f"HTTP {response.status_code}", code=response.status_code)

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
