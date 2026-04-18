"""Pydantic output models for curated datasets."""

from typing import Literal

from pydantic import BaseModel, Field


class PlayerDashboardRow(BaseModel):
    """One row in the player dashboard curated table."""

    player_id: int
    web_name: str
    full_name: str
    team_name: str
    team_short: str
    position: str = Field(pattern=r"^(GKP|DEF|MID|FWD)$")

    # Performance
    total_points: int
    minutes: int
    goals_scored: int
    assists: int
    clean_sheets: int
    bonus: int
    form: float
    points_per_game: float

    # Value
    price: float = Field(description="Price in millions (now_cost / 10)")
    ownership_pct: float
    points_per_million: float
    transfers_in: int
    transfers_out: int
    net_transfers: int

    # xStats (nullable — ~52% Understat coverage)
    xg: float | None = None
    xa: float | None = None
    npxg: float | None = None
    xg_delta: float | None = Field(default=None, description="goals_scored - xG (overperformance)")

    # ICT
    influence: float
    creativity: float
    threat: float
    ict_index: float

    # LLM enrichments (nullable — only top 300)
    form_trend: str | None = None
    form_confidence: float | None = None
    llm_summary: str | None = None
    injury_risk: int | None = Field(default=None, ge=0, le=10)
    injury_reasoning: str | None = None
    sentiment_label: str | None = None
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    key_themes: list[str] | None = None

    # Fixtures
    fdr_next_3: float | None = None
    fdr_next_6: float | None = None
    best_gameweeks: list[int] | None = None
    fixture_recommendation: str | None = None

    # Composite
    fpl_score: float = Field(ge=0.0, le=100.0)
    fpl_score_rank: int = Field(ge=1)

    # Score components (weighted contributions to fpl_score)
    score_form: float | None = None
    score_value: float | None = None
    score_fixtures: float | None = None
    score_xg: float | None = None
    score_momentum: float | None = None
    score_ict: float | None = None
    score_injury: float | None = None

    # Partition keys
    season: str
    gameweek: int

    # Gameweek the dashboard advises on (typically gameweek + 1; None at end-of-season).
    # Used by the Captain Picker UI as its page label.
    advice_gameweek: int | None = None


class FixtureTickerRow(BaseModel):
    """One row in the fixture ticker — one team's fixture in one gameweek."""

    team_id: int
    team_name: str
    team_short: str
    gameweek: int
    opponent: str
    opponent_short: str
    is_home: bool
    fdr: int = Field(ge=1, le=5)
    kickoff_time: str | None = None
    season: str


class TransferPickRow(BaseModel):
    """One row in the transfer picks table."""

    player_id: int
    web_name: str
    team_name: str
    team_short: str
    position: str
    price: float
    fpl_score: float
    fpl_score_rank: int
    recommendation: Literal["buy", "sell", "hold", "watch"]
    recommendation_reasons: list[str]
    form: float
    form_trend: str | None = None
    injury_risk: int | None = None
    fdr_next_3: float | None = None
    net_transfers: int
    season: str
    gameweek: int


class TeamStrengthRow(BaseModel):
    """One row in the team strength table — one per team."""

    team_id: int
    team_name: str
    team_short: str
    avg_fpl_score: float
    total_points: int
    avg_form: float
    squad_value: float = Field(description="Sum of player prices in millions")
    top_scorer_id: int
    top_scorer_name: str
    top_scorer_points: int
    avg_fdr_remaining: float | None = None
    player_count: int
    enriched_player_count: int
    season: str
    gameweek: int
