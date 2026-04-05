"""Resolve the current FPL gameweek from the official API.

The FPL API bootstrap-static endpoint contains an `events` array where each
event has `id` (gameweek number), `finished` (bool), and `is_current` (bool).
"""

import logging

import httpx

logger = logging.getLogger(__name__)

FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


class GameweekInfo:
    """Resolved gameweek information from the FPL API."""

    def __init__(self, current_gw: int, latest_finished_gw: int, season: str) -> None:
        self.current_gw = current_gw
        self.latest_finished_gw = latest_finished_gw
        self.season = season

    def to_dict(self) -> dict[str, int | str]:
        return {
            "current_gw": self.current_gw,
            "latest_finished_gw": self.latest_finished_gw,
            "season": self.season,
        }


async def resolve_gameweek(season: str = "2025-26") -> GameweekInfo:
    """Fetch bootstrap data and determine the current and latest finished gameweek.

    Args:
        season: Season identifier for the pipeline (passed through, not validated
                against the API since the FPL API doesn't expose season strings).

    Returns:
        GameweekInfo with current_gw and latest_finished_gw.

    Raises:
        ValueError: If no gameweek data is found in the API response.
    """
    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
        timeout=30.0,
    ) as client:
        response = await client.get(FPL_BOOTSTRAP_URL)
        response.raise_for_status()
        data = response.json()

    events = data.get("events", [])
    if not events:
        raise ValueError("No events found in FPL bootstrap data")

    current_gw = 0
    latest_finished_gw = 0

    for event in events:
        if event.get("is_current"):
            current_gw = event["id"]
        if event.get("finished"):
            latest_finished_gw = max(latest_finished_gw, event["id"])

    if current_gw == 0:
        # Season hasn't started or all gameweeks are done
        current_gw = latest_finished_gw

    logger.info(
        "Resolved gameweek: current=%d, latest_finished=%d",
        current_gw,
        latest_finished_gw,
    )

    return GameweekInfo(
        current_gw=current_gw,
        latest_finished_gw=latest_finished_gw,
        season=season,
    )
