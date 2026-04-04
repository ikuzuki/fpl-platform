"""Fixture domain models."""

from datetime import datetime

from pydantic import BaseModel, Field


class Fixture(BaseModel):
    """FPL fixture data."""

    id: int
    gameweek: int = Field(ge=1, le=38)
    home_team: str
    away_team: str
    home_difficulty: int = Field(ge=1, le=5, description="FDR rating 1-5")
    away_difficulty: int = Field(ge=1, le=5, description="FDR rating 1-5")
    kickoff_time: datetime | None = None
