"""FPL date and season utilities."""

from datetime import datetime


def current_season() -> str:
    """Return the current FPL season string (e.g. '2025-26').

    The FPL season starts in August and ends in May the following year.
    """
    now = datetime.now()
    if now.month >= 8:
        return f"{now.year}-{str(now.year + 1)[-2:]}"
    return f"{now.year - 1}-{str(now.year)[-2:]}"


def gameweek_deadline(season: str, gameweek: int) -> str:
    """Return a placeholder deadline string for a gameweek.

    In production, this would query the FPL API for actual deadlines.
    """
    start_year = int(season.split("-")[0])
    return f"{start_year}-08-01T00:00:00Z (GW{gameweek} placeholder)"


def is_gameweek_active() -> bool:
    """Check if a gameweek is currently active.

    In production, this would check the FPL API live endpoint.
    """
    now = datetime.now()
    return now.month >= 8 or now.month <= 5
