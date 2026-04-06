"""Curation service configuration extending base FPL settings."""

from functools import lru_cache

from fpl_lib.core.config import FPLSettings

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

TOTAL_GAMEWEEKS = 38

DEFAULT_FPL_SCORE_WEIGHTS: dict[str, float] = {
    "form": 0.25,
    "value": 0.15,
    "fixtures": 0.15,
    "xg_overperformance": 0.15,
    "ownership_momentum": 0.10,
    "ict": 0.10,
    "injury_risk": 0.10,
}


class CurateSettings(FPLSettings):
    """Settings for the curation service."""

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    FPL_SCORE_WEIGHTS: dict[str, float] = DEFAULT_FPL_SCORE_WEIGHTS


@lru_cache
def get_curate_settings() -> CurateSettings:
    """Return cached curation settings instance."""
    return CurateSettings()
