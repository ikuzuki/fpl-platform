"""Pydantic models for validating LLM enricher outputs."""

from typing import Literal

from pydantic import BaseModel, Field


class PlayerSummaryOutput(BaseModel):
    """Validated output from the player summary enricher."""

    summary: str = Field(min_length=20)
    form_trend: Literal["improving", "stable", "declining"]
    confidence: float = Field(ge=0.0, le=1.0)


class InjurySignalOutput(BaseModel):
    """Validated output from the injury signal enricher."""

    risk_score: int = Field(ge=0, le=10)
    reasoning: str = Field(min_length=1)
    injury_type: str | None = None
    sources: list[str] = []


class SentimentOutput(BaseModel):
    """Validated output from the sentiment enricher."""

    sentiment: Literal["very positive", "positive", "neutral", "negative", "very negative", "mixed"]
    score: float = Field(ge=-1.0, le=1.0)
    key_themes: list[str] = []


class FixtureOutlookOutput(BaseModel):
    """Validated output from the fixture outlook enricher."""

    difficulty_score: int = Field(ge=1, le=5)
    recommendation: str = Field(min_length=1)
    best_gameweeks: list[int] = []
